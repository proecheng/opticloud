from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_traffic_replay_plan.py"
PLAN_PATH = REPO_ROOT / "tools" / "traffic_replay" / "replay_plan.json"
CAPTURE_EXAMPLE_PATH = REPO_ROOT / "tools" / "traffic_replay" / "capture_fixture.example.json"
CAPTURE_SCHEMA_PATH = REPO_ROOT / "tools" / "traffic_replay" / "capture_fixture.schema.json"
EVIDENCE_EXAMPLE_PATH = REPO_ROOT / "tools" / "traffic_replay" / "evidence_manifest.example.json"
EVIDENCE_SCHEMA_PATH = REPO_ROOT / "tools" / "traffic_replay" / "evidence_manifest.schema.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "production-traffic-replay.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_traffic_replay_plan", VALIDATOR_PATH)
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


def _real_capture_from_example() -> dict[str, Any]:
    capture = _load_json(CAPTURE_EXAMPLE_PATH)
    capture["example_only"] = False
    capture["redaction_profile"] = "standard-redaction-v1"
    return capture


def _real_evidence_from_example(capture: dict[str, Any] | None = None) -> dict[str, Any]:
    validator = _load_validator()
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)
    capture_data = capture if capture is not None else _real_capture_from_example()
    evidence["example_only"] = False
    evidence["capture_id"] = capture_data["capture_id"]
    evidence["redaction_profile"] = capture_data["redaction_profile"]
    evidence["capture_fixture_sha256"] = validator.canonical_sha256(capture_data)
    return evidence


def test_committed_traffic_replay_plan_validates_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "traffic replay plan OK" in result.stdout


def test_plan_pins_lanes_sources_and_redaction_policy() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)

    assert validator.validate_plan(plan) == []
    assert plan["dataset_version"] == "prod_traffic_replay_plan_v1"
    assert plan["source_story"] == "M3.6e"
    assert plan["source_decision"] == "RE2-7"
    assert [lane["lane"] for lane in plan["lanes"]] == [
        "api_gateway_public",
        "chat_streaming",
        "contract_fuzz",
    ]


def test_plan_lane_and_threshold_family_drift_is_rejected() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    plan["lanes"][0]["lane"] = "api_gateway_private"
    plan["lanes"][1]["threshold_reference"] = "M3.6d"
    plan["redaction_required"] = False

    errors = validator.validate_plan(plan)

    _assert_invalid(errors, "lane order must be api_gateway_public, chat_streaming, contract_fuzz")
    _assert_invalid(errors, "chat_streaming threshold_reference must be M3.6a")
    _assert_invalid(errors, "redaction_required must be True")


def test_capture_schema_and_example_are_valid() -> None:
    validator = _load_validator()
    schema = _load_json(CAPTURE_SCHEMA_PATH)
    capture = _load_json(CAPTURE_EXAMPLE_PATH)

    assert validator.validate_capture_schema(schema) == []
    assert validator.validate_capture_fixture(capture, source="capture-example") == []
    assert "(?!.*https?://)" in schema["$defs"]["pathTemplate"]["pattern"]


def test_capture_example_is_not_real_fixture() -> None:
    validator = _load_validator()
    capture = _load_json(CAPTURE_EXAMPLE_PATH)

    errors = validator.validate_capture_fixture(
        capture,
        source="capture-example",
        real_fixture=True,
    )

    _assert_invalid(errors, "real capture fixture must set example_only=false")
    _assert_invalid(errors, "real capture fixture must not use synthetic example profile")


def test_capture_rejects_pii_secrets_raw_hosts_and_prompt_text() -> None:
    validator = _load_validator()
    capture = _load_json(CAPTURE_EXAMPLE_PATH)
    capture["requests"][0]["header_shape"]["Authorization"] = "Bearer abcdef1234567890"
    capture["requests"][0]["body_shape"]["accessToken"] = "shape"
    capture["requests"][1]["query_shape"]["email"] = "student@example.com"
    capture["requests"][2]["path_template"] = "https://api.opticloud.cn/v1/chat/stream"
    capture["requests"][2]["body_shape"]["prompt"] = "customer prompt with raw content"
    jwt_parts = [
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "eyJzdWIiOiJ1c2VyLTEyMyJ9",
        "signature123",
    ]
    capture["requests"][2]["body_shape"]["jwt_shape"] = ".".join(jwt_parts)

    errors = validator.validate_capture_fixture(capture, source="capture-example")

    _assert_invalid(errors, "forbidden bearer token")
    _assert_invalid(errors, "forbidden secret-like key")
    _assert_invalid(errors, "forbidden email")
    _assert_invalid(errors, "path_template must not contain a host")
    _assert_invalid(errors, "forbidden prompt-like key")
    _assert_invalid(errors, "forbidden jwt")


def test_capture_rejects_missing_and_extra_contract_fields() -> None:
    validator = _load_validator()
    capture = _load_json(CAPTURE_EXAMPLE_PATH)
    del capture["generated_by"]
    capture["unexpected"] = "drift"
    del capture["requests"][0]["weight"]
    capture["requests"][0]["unexpected"] = "drift"

    errors = validator.validate_capture_fixture(capture, source="capture-example")

    _assert_invalid(errors, "missing required field generated_by")
    _assert_invalid(errors, "unexpected field unexpected")
    _assert_invalid(errors, "request missing required field weight")
    _assert_invalid(errors, "request unexpected field unexpected")


def test_evidence_schema_and_example_are_valid() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    capture = _load_json(CAPTURE_EXAMPLE_PATH)
    schema = _load_json(EVIDENCE_SCHEMA_PATH)
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)

    assert validator.validate_evidence_schema(schema) == []
    assert (
        validator.validate_evidence_manifest(
            evidence,
            plan,
            capture,
            validator.canonical_sha256(plan),
            validator.canonical_sha256(capture),
            source="evidence-example",
            real_evidence=False,
        )
        == []
    )


def test_evidence_example_is_not_real_evidence() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    capture = _load_json(CAPTURE_EXAMPLE_PATH)
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)

    errors = validator.validate_evidence_manifest(
        evidence,
        plan,
        capture,
        validator.canonical_sha256(plan),
        validator.canonical_sha256(capture),
        source="evidence-example",
        real_evidence=True,
    )

    _assert_invalid(errors, "real replay evidence must set example_only=false")


def test_real_capture_and_evidence_path_mode_accept_redacted_run() -> None:
    capture = _real_capture_from_example()
    evidence = _real_evidence_from_example(capture)
    run_dir = REPO_ROOT / "reports" / "prod-traffic-replay" / "test-replay-20260526"
    run_dir.mkdir(parents=True, exist_ok=True)
    capture_path = run_dir / "capture_fixture.json"
    evidence_path = run_dir / "evidence_manifest.json"
    capture["capture_id"] = "test-replay-20260526"
    evidence["run_id"] = "test-replay-20260526"
    evidence["capture_id"] = capture["capture_id"]
    for key, value in evidence["artifacts"].items():
        evidence["artifacts"][key] = value.replace(
            "example-prod-replay-20260526", "test-replay-20260526"
        )
    validator = _load_validator()
    evidence["capture_fixture_sha256"] = validator.canonical_sha256(capture)
    capture_path.write_text(
        json.dumps(capture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--evidence", str(evidence_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    try:
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        evidence_path.unlink(missing_ok=True)
        capture_path.unlink(missing_ok=True)
        run_dir.rmdir()


def test_evidence_rejects_artifact_path_traversal_and_wrong_extensions() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    capture = _load_json(CAPTURE_EXAMPLE_PATH)
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)
    evidence["artifacts"]["replay_report"] = "reports/prod-traffic-replay/other/../report.txt"
    evidence["artifacts"]["redaction_audit"] = (
        "reports/prod-traffic-replay/example-prod-replay-20260526/redaction.html"
    )

    errors = validator.validate_evidence_manifest(
        evidence,
        plan,
        capture,
        validator.canonical_sha256(plan),
        validator.canonical_sha256(capture),
        source="evidence",
        real_evidence=False,
    )

    _assert_invalid(errors, "must not traverse")
    _assert_invalid(
        errors, "must stay under reports/prod-traffic-replay/example-prod-replay-20260526/"
    )
    _assert_invalid(errors, "replay_report must be .html or .json")
    _assert_invalid(errors, "redaction_audit must be .json")


def test_evidence_rejects_hash_and_capture_metadata_mismatch() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    capture = _load_json(CAPTURE_EXAMPLE_PATH)
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)
    evidence["plan_sha256"] = "0" * 64
    evidence["capture_fixture_sha256"] = "1" * 64
    evidence["capture_id"] = "different-capture"
    evidence["redaction_profile"] = "different-profile"

    errors = validator.validate_evidence_manifest(
        evidence,
        plan,
        capture,
        validator.canonical_sha256(plan),
        validator.canonical_sha256(capture),
        source="evidence",
        real_evidence=False,
    )

    _assert_invalid(errors, "plan_sha256 does not match")
    _assert_invalid(errors, "capture_fixture_sha256 does not match")
    _assert_invalid(errors, "capture_id must match capture fixture")
    _assert_invalid(errors, "redaction_profile must match capture fixture")


def test_evidence_rejects_lane_drift_error_rate_redaction_and_drift_failures() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    capture = _real_capture_from_example()
    evidence = _real_evidence_from_example(capture)
    evidence["duration_seconds"] = 0
    evidence["lane_results"][0]["success_count"] = 11
    evidence["lane_results"][0]["request_count"] = 10
    evidence["lane_results"][0]["http_error_rate"] = 0.011
    evidence["lane_results"][1]["http_error_rate"] = 0.021
    evidence["lane_results"][1]["replay_drift_rate"] = 0.03
    evidence["lane_results"][2]["redaction_violation_count"] = 1
    evidence["lane_results"][2]["lane"] = "extra_lane"

    errors = validator.validate_evidence_manifest(
        evidence,
        plan,
        capture,
        validator.canonical_sha256(plan),
        validator.canonical_sha256(capture),
        source="evidence-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "duration_seconds must be greater than 0")
    _assert_invalid(errors, "api_gateway_public success_count exceeds request_count")
    _assert_invalid(errors, "api_gateway_public http_error_rate fails threshold")
    _assert_invalid(errors, "chat_streaming http_error_rate fails threshold")
    _assert_invalid(errors, "chat_streaming replay_drift_rate fails threshold")
    _assert_invalid(errors, "contract_fuzz redaction_violation_count must be 0")
    _assert_invalid(errors, "lane results must match plan exactly")


def test_evidence_rejects_cross_story_pass_claims_and_seconds_metrics() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    capture = _load_json(CAPTURE_EXAMPLE_PATH)
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)
    evidence["g6_hard_gate_pass"] = True
    evidence["lane_results"][0]["latency_seconds"] = 1

    errors = validator.validate_evidence_manifest(
        evidence,
        plan,
        capture,
        validator.canonical_sha256(plan),
        validator.canonical_sha256(capture),
        source="evidence",
        real_evidence=False,
    )

    _assert_invalid(errors, "replay evidence cannot claim unrelated pass status")
    _assert_invalid(errors, "metric latency_seconds must use ms fields")


def test_evidence_rejects_missing_extra_and_lane_contract_fields() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    capture = _load_json(CAPTURE_EXAMPLE_PATH)
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)
    del evidence["commit_sha"]
    evidence["unexpected"] = "drift"
    del evidence["lane_results"][0]["p95_ms"]
    evidence["lane_results"][0]["unexpected"] = "drift"

    errors = validator.validate_evidence_manifest(
        evidence,
        plan,
        capture,
        validator.canonical_sha256(plan),
        validator.canonical_sha256(capture),
        source="evidence",
        real_evidence=False,
    )

    _assert_invalid(errors, "missing required field commit_sha")
    _assert_invalid(errors, "unexpected field unexpected")
    _assert_invalid(errors, "lane result missing required field p95_ms")
    _assert_invalid(errors, "lane result unexpected field unexpected")


def test_path_modes_reject_m3_6a_to_m3_6d_report_directories() -> None:
    validator = _load_validator()

    assert (
        validator.validate_capture_path_mode(
            Path("reports/prod-traffic-replay/run-123/capture_fixture.json")
        )
        == []
    )
    assert (
        validator.validate_evidence_path_mode(
            Path("reports/prod-traffic-replay/run-123/evidence_manifest.json")
        )
        == []
    )
    for wrong_path in (
        Path("reports/chat-load/run-123/evidence_manifest.json"),
        Path("reports/chat-single-node/run-123/evidence_manifest.json"),
        Path("reports/chat-incident-fallback/run-123/evidence_manifest.json"),
        Path("reports/api-gateway-perf/run-123/evidence_manifest.json"),
    ):
        _assert_invalid(
            validator.validate_evidence_path_mode(wrong_path),
            "traffic replay evidence path must be",
        )


def test_evidence_validation_requires_matching_capture_fixture(tmp_path: Path) -> None:
    validator = _load_validator()
    evidence = _real_evidence_from_example()
    run_dir = REPO_ROOT / "reports" / "prod-traffic-replay" / "missing-capture-20260526"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "evidence_manifest.json"
    evidence["run_id"] = "missing-capture-20260526"
    for key, value in evidence["artifacts"].items():
        evidence["artifacts"][key] = value.replace(
            "example-prod-replay-20260526", "missing-capture-20260526"
        )
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    errors = validator.validate_all(evidence_path=path)

    try:
        _assert_invalid(errors, "matching capture_fixture.json is required")
    finally:
        path.unlink(missing_ok=True)
        run_dir.rmdir()


def test_capture_fixture_cli_mode_accepts_real_fixture(tmp_path: Path) -> None:
    capture = _real_capture_from_example()
    run_dir = REPO_ROOT / "reports" / "prod-traffic-replay" / "capture-only-20260526"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "capture_fixture.json"
    capture["capture_id"] = "capture-only-20260526"
    path.write_text(json.dumps(capture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--capture-fixture", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )

    try:
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        path.unlink(missing_ok=True)
        run_dir.rmdir()


def test_runbook_documents_operator_boundaries_and_failure_handling() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert "CI validates structure only" in runbook
    assert "does not replace M3.6a Chat staging hard-gate evidence" in runbook
    assert "M3.6d API gateway baseline evidence" in runbook
    assert "redaction-audit.json" in runbook
    assert "delete generated artifacts" in runbook
    assert "performance or contract investigation" in runbook
    assert "TRAFFIC_REPLAY_EXPORT_SOURCE" in runbook
    assert "TRAFFIC_REPLAY_STAGING_BASE_URL" in runbook
    assert "Do not commit values" in runbook


def test_ci_wires_traffic_replay_filter_and_optional_evidence_validation() -> None:
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    for expected in (
        "traffic_replay: ${{ steps.filter.outputs.traffic_replay }}",
        "traffic-replay-validation:",
        "'tools/traffic_replay/**'",
        "'scripts/validate_traffic_replay_plan.py'",
        "'tests/test_traffic_replay_plan.py'",
        "'docs/runbooks/production-traffic-replay.md'",
        "'reports/prod-traffic-replay/**'",
        "uv run python scripts/validate_traffic_replay_plan.py --capture-fixture",
        "uv run python scripts/validate_traffic_replay_plan.py --evidence",
        "uv run pytest tests/test_traffic_replay_plan.py -v",
    ):
        assert expected in workflow
