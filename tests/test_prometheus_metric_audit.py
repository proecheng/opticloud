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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_prometheus_metric_audit.py"
CONTRACT_PATH = (
    REPO_ROOT / "tools" / "prometheus_metric_audit" / "business_metric_audit_contract.json"
)
SCHEMA_PATH = (
    REPO_ROOT / "tools" / "prometheus_metric_audit" / "business_metric_audit_manifest.schema.json"
)
EXAMPLE_MANIFEST_PATH = (
    REPO_ROOT / "tools" / "prometheus_metric_audit" / "business_metric_audit_manifest.example.json"
)
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "prometheus-metric-audit.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_prometheus_metric_audit", VALIDATOR_PATH
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
    manifest["run_id"] = "test-prometheus-metric-audit-20260604"
    manifest["example_only"] = False
    manifest["generated_by"] = "redacted Prometheus metric audit evidence"
    manifest["commit_sha"] = "3eb894b"
    manifest["redaction_reviewed"] = True
    manifest["release_approved"] = True
    manifest["real_grafana_review_completed"] = True
    manifest["real_prometheus_scrape_completed"] = True
    for metric in manifest["metric_coverage"]:
        metric["status"] = "covered"
        metric["notes"] = "Redacted metric coverage evidence."
    for target in manifest["scrape_targets"]:
        target["status"] = "passed"
        target["sample_count"] = 1
    for snapshot in manifest["promql_snapshots"]:
        snapshot["status"] = "passed"
        snapshot["artifact_path"] = snapshot["artifact_path"].replace(
            "example-prometheus-metric-audit-20260604",
            "test-prometheus-metric-audit-20260604",
        )
    for review in manifest["grafana_reviews"]:
        review["review_outcome"] = "passed"
        review["screenshot_artifact_path"] = review["screenshot_artifact_path"].replace(
            "example-prometheus-metric-audit-20260604",
            "test-prometheus-metric-audit-20260604",
        )
    return manifest


def test_committed_prometheus_metric_audit_assets_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "prometheus metric audit OK" in result.stdout


def test_contract_pins_nfr_o_scope_metric_catalog_and_repo_state() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)

    assert validator.validate_contract(contract) == []
    assert contract["source_story"] == "9.2"
    assert contract["audit_version"] == "prometheus_business_metric_audit_v1"
    assert contract["standard_cadence"] == "quarterly"
    assert contract["lite_cadence"] == "annual"
    assert [item["metric_id"] for item in contract["metric_catalog"]] == list(
        validator.METRIC_IDS
    )
    latency = next(item for item in contract["metric_catalog"] if item["metric_id"] == "latency")
    assert latency["required_percentiles"] == list(validator.LATENCY_PERCENTILES)
    assert contract["observed_repo_state"] == validator.discover_repo_state()


def test_contract_rejects_metric_catalog_and_repo_state_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    contract["metric_catalog"].pop()
    contract["observed_repo_state"]["metric_declarations"].pop()

    errors = validator.validate_contract(contract)

    _assert_invalid(errors, "metric_catalog ids must match NFR-O1")
    _assert_invalid(errors, "observed_repo_state.metric_declarations drifted")


def test_schema_pins_manifest_root_and_metric_enums() -> None:
    validator = _load_validator()
    schema = _load_json(SCHEMA_PATH)

    assert validator.validate_schema(schema) == []
    assert set(schema["required"]) == validator.MANIFEST_ROOT_REQUIRED
    assert schema["$defs"]["metricId"]["enum"] == list(validator.METRIC_IDS)


def test_example_manifest_is_static_only_and_not_real_evidence() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)

    assert (
        validator.validate_manifest(
            manifest,
            contract,
            source="prometheus-example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_manifest(
        manifest,
        contract,
        source="prometheus-example",
        real_evidence=True,
    )
    _assert_invalid(errors, "example_only must be false")
    _assert_invalid(errors, "real evidence redaction_reviewed must be true")
    _assert_invalid(errors, "real evidence real_grafana_review_completed must be true")
    _assert_invalid(errors, "real evidence real_prometheus_scrape_completed must be true")


def test_static_example_rejects_fake_completion_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["real_grafana_review_completed"] = True
    manifest["real_prometheus_scrape_completed"] = True
    manifest["release_approved"] = True
    manifest["external_ticket_created"] = True
    manifest["uptime_sla_approved"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="prometheus-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "static example cannot claim real_grafana_review_completed")
    _assert_invalid(errors, "static example cannot claim real_prometheus_scrape_completed")
    _assert_invalid(errors, "static example cannot claim release_approved")
    _assert_invalid(errors, "static example cannot claim external_ticket_created")
    _assert_invalid(errors, "static example cannot claim uptime_sla_approved")


def test_real_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _real_manifest_from_example()
    run_dir = REPO_ROOT / "reports" / "prometheus-metric-audit" / manifest["run_id"]
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
            Path("reports/prometheus-metric-audit/run-123/audit_manifest.json"),
            "run-123",
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/a11y-quarterly/run-123/audit_manifest.json"),
            "run-123",
        ),
        "Prometheus metric audit evidence path must be",
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/prometheus-metric-audit/other/audit_manifest.json"),
            "run-123",
        ),
        "Prometheus metric audit evidence path must be",
    )


def test_metric_coverage_requires_all_canonical_metrics_and_latency_percentiles() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["metric_coverage"] = [
        item for item in manifest["metric_coverage"] if item["metric_id"] != "uptime"
    ]
    latency = next(item for item in manifest["metric_coverage"] if item["metric_id"] == "latency")
    latency["percentiles"] = ["p95"]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="prometheus-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "metric_coverage missing metric uptime")
    _assert_invalid(errors, "latency percentiles must be p50/p95/p99")


def test_real_evidence_rejects_planned_or_not_applicable_required_metrics() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["metric_coverage"][0]["status"] = "planned"
    manifest["metric_coverage"][1]["status"] = "not_applicable"

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="prometheus-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "real metric request_count must be covered or missing_with_ticket")
    _assert_invalid(errors, "real metric success_rate must be covered or missing_with_ticket")


def test_missing_or_failed_checks_require_ticket_refs() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["metric_coverage"][0]["status"] = "missing_with_ticket"
    manifest["metric_coverage"][0]["finding_ids"] = ["nfr-o-p2-request-count"]
    manifest["promql_snapshots"][0]["status"] = "failed"
    manifest["promql_snapshots"][0]["finding_ids"] = ["nfr-o-p2-promql"]
    manifest["grafana_reviews"][0]["review_outcome"] = "failed"
    manifest["grafana_reviews"][0]["finding_ids"] = ["nfr-o-p2-grafana"]
    manifest["findings"] = [
        {
            "finding_id": "nfr-o-p2-request-count",
            "source": "metric_coverage",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted missing metric finding.",
            "ticket_refs": [],
        },
        {
            "finding_id": "nfr-o-p2-promql",
            "source": "promql_snapshot",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted PromQL finding.",
            "ticket_refs": [],
        },
        {
            "finding_id": "nfr-o-p2-grafana",
            "source": "grafana_review",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted Grafana finding.",
            "ticket_refs": [],
        },
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="prometheus-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "finding nfr-o-p2-request-count must include ticket_refs")
    _assert_invalid(errors, "finding nfr-o-p2-promql must include ticket_refs")
    _assert_invalid(errors, "finding nfr-o-p2-grafana must include ticket_refs")


def test_release_approval_blocks_unresolved_stop_ship_findings() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["findings"] = [
        {
            "finding_id": "nfr-o-p1-latency",
            "source": "grafana_review",
            "severity": "P1",
            "status": "open",
            "summary": "Redacted stop-ship observability finding.",
            "ticket_refs": [
                {
                    "ticket_id": "NFR-O-101",
                    "owner": "SRE",
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
        source="prometheus-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "release_approved cannot be true with unresolved P1 finding")


def test_manifest_rejects_sensitive_values_paths_and_raw_metric_labels() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["tenant_id"] = "tenant-123"
    manifest["scrape_targets"][0]["notes"] = "Bearer abcdef1234567890"
    manifest["promql_snapshots"][0]["artifact_path"] = "/tmp/prometheus-raw.json"
    manifest["grafana_reviews"][0]["screenshot_artifact_path"] = (
        "reports/prometheus-metric-audit/test-prometheus-metric-audit-20260604/../leak.png"
    )
    manifest["findings"] = [
        {
            "finding_id": "nfr-o-p3-leak",
            "source": "promql_snapshot",
            "severity": "P3",
            "status": "open",
            "summary": "customer@example.com",
            "ticket_refs": [
                {
                    "ticket_id": "NFR-O-202",
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
        source="prometheus-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "forbidden sensitive key")
    _assert_invalid(errors, "forbidden bearer token")
    _assert_invalid(errors, "forbidden POSIX absolute path")
    _assert_invalid(errors, "artifact path must not traverse directories")
    _assert_invalid(errors, "forbidden email address")


def test_ci_workflow_wires_prometheus_metric_audit_job_without_soft_gate() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert validator.validate_ci_workflow(workflow) == []
    job = validator._job_block(workflow, "prometheus-metric-audit-validation")
    assert "continue-on-error" not in job


def test_ci_workflow_validation_rejects_filter_block_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace(
        "            prometheus_metric_audit:\n              - 'tools/prometheus_metric_audit/**'\n",
        "            prometheus_metric_audit:\n",
    )

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(errors, "prometheus_metric_audit filter missing 'tools/prometheus_metric_audit/**'")


def test_ci_workflow_validation_rejects_app_source_filter_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace("              - 'apps/*/src/**/*.py'\n", "")

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(errors, "prometheus_metric_audit filter missing 'apps/*/src/**/*.py'")


def test_runbook_documents_flows_redaction_tickets_and_handoffs() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    for expected in (
        "uv run python scripts/validate_prometheus_metric_audit.py",
        "reports/prometheus-metric-audit/<run_id>/audit_manifest.json",
        "quarterly",
        "annual_lite",
        "Grafana",
        "Prometheus",
        "Do not commit",
        "P0/P1/P2",
        "release approval",
        "Rollback",
        "Story 9.3",
        "Story 9.7",
    ):
        assert expected in runbook
