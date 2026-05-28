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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_j3_incident_contract.py"
CONTRACT_PATH = REPO_ROOT / "tools" / "incidents" / "j3_sre_incident_contract.json"
SCHEMA_PATH = REPO_ROOT / "tools" / "incidents" / "j3_sre_incident.schema.json"
EXAMPLE_MANIFEST_PATH = REPO_ROOT / "tools" / "incidents" / "j3_sre_incident.example.json"
M3_6C_PLAN_PATH = REPO_ROOT / "tools" / "chat_load" / "incident_fallback_plan.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "j3-sre-incident-tier3.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_j3_incident_contract", VALIDATOR_PATH)
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
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["example_only"] = False
    manifest["environment"] = "staging-incident-drill"
    manifest["generated_by"] = "redacted operator evidence"
    return manifest


def test_committed_j3_incident_contract_validates_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "j3 incident contract OK" in result.stdout


def test_contract_pins_story_slas_providers_and_m3_6c_hash() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    m3_6c_plan = _load_json(M3_6C_PLAN_PATH)

    assert validator.validate_contract(contract) == []
    assert contract["contract_version"] == "j3_sre_incident_tier3_v1"
    assert contract["source_story"] == "3.12"
    assert contract["severity"] == "P0"
    assert contract["alert_seconds_max"] == 30
    assert contract["status_page_publish_seconds_max"] == 60
    assert contract["postmortem_publish_hours_max"] == 24
    assert contract["fallback_plan"]["sha256"] == validator.canonical_sha256(m3_6c_plan)


def test_contract_rejects_provider_sla_and_hash_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    contract["primary_provider"] = "qwen-max"
    contract["status_page_publish_seconds_max"] = 120
    contract["fallback_plan"]["sha256"] = "0" * 64

    errors = validator.validate_contract(contract)

    _assert_invalid(errors, "primary_provider must be deepseek-v3.5")
    _assert_invalid(errors, "status_page_publish_seconds_max must be 60")
    _assert_invalid(errors, "fallback_plan.sha256 does not match")


def test_schema_pins_required_manifest_sections_and_status_vocabulary() -> None:
    validator = _load_validator()
    schema = _load_json(SCHEMA_PATH)

    assert validator.validate_schema(schema) == []
    assert set(schema["required"]) == validator.MANIFEST_ROOT_REQUIRED
    assert schema["$defs"]["status"]["enum"] == [
        "investigating",
        "identified",
        "monitoring",
        "resolved",
    ]


def test_example_manifest_is_valid_but_not_real_evidence() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)

    assert (
        validator.validate_manifest(
            manifest,
            contract,
            source="j3-example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_manifest(
        manifest,
        contract,
        source="j3-example",
        real_evidence=True,
    )
    _assert_invalid(errors, "real J3 incident evidence must set example_only=false")


def test_real_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _real_manifest_from_example()
    run_dir = REPO_ROOT / "reports" / "j3-sre-incident" / "test-j3-incident-20260528"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "incident_manifest.json"
    manifest["incident_id"] = "test-j3-incident-20260528"
    manifest["provider_health_snapshot"]["artifact_path"] = (
        "reports/j3-sre-incident/test-j3-incident-20260528/provider-health-snapshot.json"
    )
    manifest["postmortem_skeleton"]["public_url_path"] = (
        "/status/incidents/test-j3-incident-20260528"
    )
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


def test_manifest_rejects_status_vocab_timeline_sla_and_due_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["status_page_announcement"]["status"] = "degraded"
    manifest["timeline"]["status_page_published_utc"] = "2026-05-28T19:15:01Z"
    manifest["status_page_announcement"]["published_at_utc"] = "2026-05-28T19:15:01Z"
    manifest["timeline"]["postmortem_due_utc"] = "2026-05-29T19:14:01Z"
    manifest["postmortem_skeleton"]["publish_due_utc"] = "2026-05-29T19:14:01Z"

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="j3-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "status_page_announcement.status must be investigating")
    _assert_invalid(errors, "status_page_published_utc exceeds 60 second SLA")
    _assert_invalid(errors, "postmortem_due_utc must be exactly 24h after p0_declared_utc")


def test_manifest_rejects_timeline_order_and_metric_field_mismatch() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["timeline"]["provider_health_failed_utc"] = "2026-05-28T19:11:00Z"
    manifest["timeline"]["sre_paged_utc"] = "2026-05-28T19:10:00Z"
    manifest["timeline"]["fallback_confirmed_utc"] = "2026-05-28T19:13:30Z"
    manifest["timeline"]["fallback_decision_utc"] = "2026-05-28T19:14:00Z"
    manifest["postmortem_skeleton"]["sections"]["timeline"] = ["status_page_published_utc"]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="j3-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "provider_health_failed_utc must not precede incident_started_utc")
    _assert_invalid(errors, "sre_paged_utc must not precede provider_health_failed_utc")
    _assert_invalid(errors, "fallback_confirmed_utc must be after fallback_decision_utc")
    _assert_invalid(errors, "postmortem timeline must reference canonical timeline fields")


def test_manifest_rejects_missing_nested_fields_and_non_object_timeline() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["timeline"] = "bad timeline"
    del manifest["status_page_announcement"]["public_summary"]
    del manifest["provider_health_snapshot"]["summary"]
    del manifest["fallback_reference"]["evidence_mode"]
    del manifest["postmortem_skeleton"]["sections"]["compensation_placeholder"]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="j3-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "timeline must be an object")
    _assert_invalid(errors, "status_page_announcement missing field public_summary")
    _assert_invalid(errors, "provider_health_snapshot missing field summary")
    _assert_invalid(errors, "fallback_reference missing field evidence_mode")
    _assert_invalid(errors, "postmortem missing section compensation_placeholder")


def test_manifest_rejects_fake_completion_claims_in_static_example() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["status_page_publicly_available"] = True
    manifest["status_page_announcement"]["subscriber_webhook_sent"] = True
    manifest["status_page_announcement"]["dingtalk_webhook_called"] = True
    manifest["postmortem_skeleton"]["postmortem_publicly_published"] = True
    manifest["postmortem_skeleton"]["sections"]["credits_refunded"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="j3-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "example manifest cannot claim status_page_publicly_available")
    _assert_invalid(errors, "example manifest cannot claim subscriber_webhook_sent")
    _assert_invalid(errors, "example manifest cannot claim dingtalk_webhook_called")
    _assert_invalid(errors, "example manifest cannot claim postmortem_publicly_published")
    _assert_invalid(errors, "example manifest cannot claim credits_refunded")


def test_real_manifest_rejects_out_of_scope_completion_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["status_page_publicly_available"] = True
    manifest["status_page_announcement"]["subscriber_webhook_sent"] = True
    manifest["status_page_announcement"]["dingtalk_webhook_called"] = True
    manifest["postmortem_skeleton"]["postmortem_publicly_published"] = True
    manifest["postmortem_skeleton"]["sections"]["credits_refunded"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="j3-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "manifest cannot claim status_page_publicly_available")
    _assert_invalid(errors, "manifest cannot claim subscriber_webhook_sent")
    _assert_invalid(errors, "manifest cannot claim dingtalk_webhook_called")
    _assert_invalid(errors, "manifest cannot claim postmortem_publicly_published")
    _assert_invalid(errors, "manifest cannot claim credits_refunded")


def test_manifest_rejects_path_escape_urls_and_secret_like_values() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["provider_health_snapshot"]["artifact_path"] = "../provider-health.json"
    manifest["status_page_announcement"]["public_summary"] = (
        "Authorization: Bearer abcdef1234567890"
    )
    manifest["status_page_announcement"]["raw_url"] = "https://status.example.invalid/private"
    manifest["postmortem_skeleton"]["sections"]["impact"] = {
        "tenant_id": "tenant-secret-123",
    }
    manifest["postmortem_skeleton"]["sections"]["mitigation"] = "C:\\secrets\\incident.json"

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="j3-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "path must not traverse")
    _assert_invalid(errors, "forbidden bearer token")
    _assert_invalid(errors, "forbidden URL scheme")
    _assert_invalid(errors, "forbidden sensitive key")
    _assert_invalid(errors, "forbidden Windows absolute path")


def test_evidence_path_mode_rejects_other_report_directories_and_id_mismatch() -> None:
    validator = _load_validator()

    assert (
        validator.validate_evidence_path_mode(
            Path("reports/j3-sre-incident/run-123/incident_manifest.json"),
            "run-123",
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/chat-incident-fallback/run-123/evidence_manifest.json"),
            "run-123",
        ),
        "J3 incident evidence path must be",
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/j3-sre-incident/other-run/incident_manifest.json"),
            "run-123",
        ),
        "must match incident_id",
    )


def test_manifest_rejects_postmortem_url_and_fallback_reference_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = copy.deepcopy(_load_json(EXAMPLE_MANIFEST_PATH))
    manifest["postmortem_skeleton"]["public_url_path"] = "/status/incidents/other"
    manifest["fallback_reference"]["plan_path"] = "tools/chat_load/other_plan.json"
    manifest["fallback_reference"]["plan_sha256"] = "0" * 64
    manifest["fallback_reference"]["source_story"] = "3.12"

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="j3-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "public_url_path must match incident_id")
    _assert_invalid(errors, "fallback_reference.plan_path must be")
    _assert_invalid(errors, "fallback_reference.plan_sha256 does not match")
    _assert_invalid(errors, "fallback_reference.source_story must be M3.6c")


def test_runbook_documents_static_boundary_redaction_rollback_and_postmortem() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    for expected in (
        "Status Page `Investigating`",
        "not the Epic 8.A production status page",
        "docs/runbooks/chat-incident-fallback.md",
        "reports/j3-sre-incident/<incident_id>/incident_manifest.json",
        "Do not commit",
        "Rollback",
        "Postmortem review",
        "compensation placeholder",
        "does not call DingTalk",
    ):
        assert expected in runbook


def test_ci_wires_j3_incident_filter_and_optional_evidence_validation() -> None:
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    for expected in (
        "j3_incident_contract: ${{ steps.filter.outputs.j3_incident_contract }}",
        "j3-incident-contract-validation:",
        "'tools/incidents/**'",
        "'scripts/validate_j3_incident_contract.py'",
        "'tests/test_j3_incident_contract.py'",
        "'docs/runbooks/j3-sre-incident-tier3.md'",
        "'reports/j3-sre-incident/**'",
        "uv run python scripts/validate_j3_incident_contract.py --evidence",
        "uv run pytest tests/test_j3_incident_contract.py -v",
    ):
        assert expected in workflow
