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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_governance_dashboard.py"
CONTRACT_PATH = REPO_ROOT / "tools" / "governance_dashboard" / "governance_dashboard_contract.json"
SCHEMA_PATH = (
    REPO_ROOT / "tools" / "governance_dashboard" / "governance_dashboard_manifest.schema.json"
)
EXAMPLE_MANIFEST_PATH = (
    REPO_ROOT / "tools" / "governance_dashboard" / "governance_dashboard_manifest.example.json"
)
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "governance-dashboard.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_governance_dashboard", VALIDATOR_PATH)
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
    manifest["run_id"] = "test-governance-dashboard-20260605"
    manifest["example_only"] = False
    manifest["generated_by"] = "redacted governance dashboard evidence"
    manifest["commit_sha"] = "b2fe321"
    manifest["redaction_reviewed"] = True
    manifest["release_approved"] = True
    manifest["real_grafana_dashboard_published"] = False
    manifest["real_datasource_connected"] = False
    manifest["real_role_review_completed"] = True
    manifest["real_evidence_aggregation_completed"] = True
    manifest["overall_rollup_status"] = "green"
    for rollup in manifest["kpi_rollups"]:
        rollup["status"] = "green"
    for source in manifest["source_snapshots"]:
        source["status"] = "current"
        source["artifact_path"] = source["artifact_path"].replace(
            "example-governance-dashboard-20260605",
            "test-governance-dashboard-20260605",
        )
    for panel in manifest["panel_results"]:
        panel["status"] = "green"
        panel["artifact_path"] = panel["artifact_path"].replace(
            "example-governance-dashboard-20260605",
            "test-governance-dashboard-20260605",
        )
    for review in manifest["grafana_reviews"]:
        review["status"] = "passed"
        review["artifact_path"] = review["artifact_path"].replace(
            "example-governance-dashboard-20260605",
            "test-governance-dashboard-20260605",
        )
    for review in manifest["role_reviews"]:
        review["status"] = "passed"
    return manifest


def test_committed_governance_dashboard_assets_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "governance dashboard OK" in result.stdout


def test_contract_pins_sources_roles_kpis_panels_and_observed_state() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)

    assert validator.validate_contract(contract) == []
    assert contract["source_story"] == "9.7"
    assert contract["dashboard_version"] == "governance_dashboard_v1"
    assert [item["source_id"] for item in contract["upstream_sources"]] == list(
        validator.UPSTREAM_SOURCE_IDS
    )
    assert contract["viewer_roles"] == list(validator.VIEWER_ROLES)
    assert contract["kpi_groups"] == list(validator.KPI_GROUPS)
    assert contract["observed_upstream_state"] == validator.discover_upstream_state()


def test_contract_rejects_upstream_kpi_role_and_panel_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    contract["upstream_sources"].pop()
    contract["viewer_roles"].remove("Compliance")
    contract["kpi_groups"].remove("error_i18n")
    contract["panel_catalog"][0]["upstream_source_id"] = "unknown_source"

    errors = validator.validate_contract(contract)

    _assert_invalid(errors, "upstream_sources ids must match")
    _assert_invalid(errors, "viewer roles drifted")
    _assert_invalid(errors, "KPI groups drifted")
    _assert_invalid(errors, "references invalid upstream_source_id")


def test_contract_rejects_observed_upstream_state_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    contract["observed_upstream_state"]["a11y_quarterly_audit"]["source_story"] = "9.x"

    errors = validator.validate_contract(contract)

    _assert_invalid(errors, "observed_upstream_state drifted")


def test_schema_pins_manifest_root_and_enums() -> None:
    validator = _load_validator()
    schema = _load_json(SCHEMA_PATH)

    assert validator.validate_schema(schema) == []
    assert set(schema["required"]) == validator.MANIFEST_ROOT_REQUIRED
    assert schema["$defs"]["sourceId"]["enum"] == list(validator.UPSTREAM_SOURCE_IDS)
    assert schema["$defs"]["kpiGroup"]["enum"] == list(validator.KPI_GROUPS)
    assert schema["$defs"]["viewerRole"]["enum"] == list(validator.VIEWER_ROLES)


def test_example_manifest_is_static_only_and_not_real_evidence() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)

    assert (
        validator.validate_manifest(
            manifest,
            contract,
            source="governance-dashboard-example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_manifest(
        manifest,
        contract,
        source="governance-dashboard-example",
        real_evidence=True,
    )

    _assert_invalid(errors, "example_only must be false")
    _assert_invalid(errors, "real evidence redaction_reviewed must be true")
    _assert_invalid(errors, "real evidence real_role_review_completed must be true")


def test_static_example_rejects_fake_completion_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["real_grafana_dashboard_published"] = True
    manifest["real_datasource_connected"] = True
    manifest["real_role_review_completed"] = True
    manifest["real_evidence_aggregation_completed"] = True
    manifest["release_approved"] = True
    manifest["external_ticket_created"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="governance-dashboard-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "static example cannot claim real_grafana_dashboard_published")
    _assert_invalid(errors, "static example cannot claim real_datasource_connected")
    _assert_invalid(errors, "static example cannot claim real_role_review_completed")
    _assert_invalid(errors, "static example cannot claim real_evidence_aggregation_completed")
    _assert_invalid(errors, "static example cannot claim release_approved")
    _assert_invalid(errors, "static example cannot claim external_ticket_created")


def test_real_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _real_manifest_from_example()
    run_dir = REPO_ROOT / "reports" / "governance-dashboard" / manifest["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "dashboard_manifest.json"
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
            Path("reports/governance-dashboard/run-123/dashboard_manifest.json"),
            "run-123",
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/prometheus-metric-audit/run-123/dashboard_manifest.json"),
            "run-123",
        ),
        "Governance dashboard evidence path must be",
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/governance-dashboard/other/dashboard_manifest.json"),
            "run-123",
        ),
        "Governance dashboard evidence path must be",
    )


def test_real_evidence_does_not_require_real_grafana_publication_claim() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["real_grafana_dashboard_published"] = False
    manifest["real_datasource_connected"] = False

    assert (
        validator.validate_manifest(
            manifest,
            contract,
            source="governance-dashboard-real",
            real_evidence=True,
        )
        == []
    )


def test_manifest_requires_all_sources_kpis_panels_and_roles() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["source_snapshots"] = [
        item for item in manifest["source_snapshots"] if item["source_id"] != "error_i18n_audit"
    ]
    manifest["kpi_rollups"] = [
        item for item in manifest["kpi_rollups"] if item["kpi_group"] != "security"
    ]
    manifest["panel_results"] = [
        item
        for item in manifest["panel_results"]
        if item["panel_id"] != "error-i18n-audit-state"
    ]
    manifest["role_reviews"] = [
        item for item in manifest["role_reviews"] if item["viewer_role"] != "Compliance"
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="governance-dashboard-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "source_snapshots missing source error_i18n_audit")
    _assert_invalid(errors, "kpi_rollups missing KPI group security")
    _assert_invalid(errors, "panel_results missing panel error-i18n-audit-state")
    _assert_invalid(errors, "role_reviews missing role Compliance")


def test_missing_stale_failed_and_red_rollups_require_ticket_refs() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["source_snapshots"][0]["status"] = "stale"
    manifest["source_snapshots"][0]["finding_ids"] = ["gov-p2-source"]
    manifest["panel_results"][0]["status"] = "red"
    manifest["panel_results"][0]["finding_ids"] = ["gov-p1-panel"]
    manifest["grafana_reviews"][0]["status"] = "failed"
    manifest["grafana_reviews"][0]["finding_ids"] = ["gov-p2-grafana"]
    manifest["role_reviews"][0]["status"] = "missing"
    manifest["role_reviews"][0]["finding_ids"] = ["gov-p2-role"]
    manifest["kpi_rollups"][0]["status"] = "yellow"
    manifest["kpi_rollups"][0]["finding_ids"] = ["gov-p2-rollup"]
    manifest["findings"] = [
        {
            "finding_id": "gov-p2-source",
            "source": "source_snapshot",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted stale source finding.",
            "ticket_refs": [],
        },
        {
            "finding_id": "gov-p1-panel",
            "source": "panel_result",
            "severity": "P1",
            "status": "open",
            "summary": "Redacted red panel finding.",
            "ticket_refs": [],
        },
        {
            "finding_id": "gov-p2-grafana",
            "source": "grafana_review",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted Grafana review finding.",
            "ticket_refs": [],
        },
        {
            "finding_id": "gov-p2-role",
            "source": "role_review",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted role review finding.",
            "ticket_refs": [],
        },
        {
            "finding_id": "gov-p2-rollup",
            "source": "kpi_rollup",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted KPI rollup finding.",
            "ticket_refs": [],
        },
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="governance-dashboard-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "finding gov-p2-source must include ticket_refs")
    _assert_invalid(errors, "finding gov-p1-panel must include ticket_refs")
    _assert_invalid(errors, "finding gov-p2-grafana must include ticket_refs")
    _assert_invalid(errors, "finding gov-p2-role must include ticket_refs")
    _assert_invalid(errors, "finding gov-p2-rollup must include ticket_refs")


def test_release_approval_blocks_unresolved_stop_ship_findings() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["findings"] = [
        {
            "finding_id": "gov-p0-rollup",
            "source": "dashboard_rollup",
            "severity": "P0",
            "status": "open",
            "summary": "Redacted stop-ship dashboard finding.",
            "ticket_refs": [
                {
                    "ticket_id": "GOV-DASH-101",
                    "owner": "SRE",
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
        source="governance-dashboard-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "release_approved cannot be true with unresolved P0 finding")


def test_manifest_rejects_sensitive_values_and_invalid_datasource_modes() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["grafana_token"] = "grafana-token-abcdef123456"
    manifest["source_snapshots"][0]["artifact_path"] = "/tmp/raw-dashboard.json"
    manifest["panel_results"][0]["data_source_mode"] = "grafana_api"
    manifest["panel_results"][0]["query_or_transform"] = "Bearer abcdef1234567890"
    manifest["grafana_reviews"][0]["artifact_path"] = (
        "reports/governance-dashboard/test-governance-dashboard-20260605/../leak.png"
    )
    manifest["findings"] = [
        {
            "finding_id": "gov-p3-leak",
            "source": "panel_result",
            "severity": "P3",
            "status": "open",
            "summary": "customer@example.com",
            "ticket_refs": [
                {
                    "ticket_id": "GOV-DASH-202",
                    "owner": "SRE",
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
        source="governance-dashboard-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "forbidden sensitive key")
    _assert_invalid(errors, "forbidden POSIX absolute path")
    _assert_invalid(errors, "invalid data_source_mode")
    _assert_invalid(errors, "forbidden bearer token")
    _assert_invalid(errors, "artifact path must not traverse directories")
    _assert_invalid(errors, "forbidden email address")


def test_ci_workflow_wires_governance_dashboard_job_without_soft_gate() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert validator.validate_ci_workflow(workflow) == []
    job = validator._job_block(workflow, "governance-dashboard-validation")
    assert "continue-on-error" not in job


def test_ci_workflow_validation_rejects_filter_block_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace(
        "            governance_dashboard:\n              - 'tools/governance_dashboard/**'\n",
        "            governance_dashboard:\n",
    )

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(errors, "governance_dashboard filter missing 'tools/governance_dashboard/**'")


def test_ci_workflow_validation_rejects_upstream_filter_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace("              - 'tools/error_i18n_audit/**'\n", "")

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(errors, "governance_dashboard filter missing 'tools/error_i18n_audit/**'")


def test_runbook_documents_dashboard_flow_sources_redaction_tickets_and_handoff() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    for expected in (
        "uv run python scripts/validate_governance_dashboard.py",
        "reports/governance-dashboard/<run_id>/dashboard_manifest.json",
        "Grafana-ready",
        "PM",
        "Security",
        "UX",
        "SRE",
        "Compliance",
        "Do not commit",
        "P0/P1/P2",
        "release approval",
        "Rollback",
        "Story 9.8",
    ):
        assert expected in runbook
