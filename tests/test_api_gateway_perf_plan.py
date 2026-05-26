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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_api_gateway_perf_plan.py"
PLAN_PATH = REPO_ROOT / "tools" / "api_gateway_perf" / "perf_baseline_plan.json"
EXAMPLE_MANIFEST_PATH = REPO_ROOT / "tools" / "api_gateway_perf" / "evidence_manifest.example.json"
SCHEMA_PATH = REPO_ROOT / "tools" / "api_gateway_perf" / "evidence_manifest.schema.json"
LOCUSTFILE_PATH = REPO_ROOT / "tools" / "api_gateway_perf" / "locustfile.py"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_api_gateway_perf_plan", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_locustfile() -> ModuleType:
    spec = importlib.util.spec_from_file_location("api_gateway_perf_locustfile", LOCUSTFILE_PATH)
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
    return manifest


def test_committed_api_gateway_perf_plan_validates_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "api gateway perf plan OK" in result.stdout


def test_plan_pins_profile_endpoints_thresholds_and_observability() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)

    assert validator.validate_plan(plan) == []
    assert plan["dataset_version"] == "api_gateway_perf_baseline_v1"
    assert plan["source_story"] == "M3.6d"
    assert plan["profile"]["users"] == 100
    assert plan["profile"]["run_time_seconds"] == 1800
    endpoint_classes = [endpoint["endpoint_class"] for endpoint in plan["endpoints"]]
    assert endpoint_classes == ["algorithms_public", "auth_api_keys", "business_demo"]


def test_plan_endpoint_and_threshold_drift_is_rejected() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    plan["endpoints"][0]["path"] = "/v1/algorithm"
    plan["endpoints"][1]["p95_threshold_ms"] = 300
    plan["endpoints"][2]["auth_mode"] = "api_key_bearer_env"

    errors = validator.validate_plan(plan)

    _assert_invalid(errors, "algorithms_public path must be /v1/algorithms")
    _assert_invalid(errors, "auth_api_keys p95_threshold_ms must be 200")
    _assert_invalid(errors, "business_demo auth_mode must be none")


def test_plan_rejects_secret_like_values() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    plan["runtime"] = {"api_key": "sk-test1234567890abcdef"}

    errors = validator.validate_plan(plan)

    _assert_invalid(errors, "forbidden secret-like key")
    _assert_invalid(errors, "forbidden generic sk key")


def test_schema_pins_artifacts_endpoint_results_and_metric_fields() -> None:
    validator = _load_validator()
    schema = _load_json(SCHEMA_PATH)

    assert validator.validate_schema(schema) == []
    assert "(?!.*\\.\\.)" in schema["$defs"]["artifactPath"]["pattern"]
    metrics_required = set(schema["$defs"]["endpointResult"]["required"])
    assert "locust_p95_ms" in metrics_required
    assert "prometheus_histogram_quantile_p95_ms" in metrics_required


def test_example_manifest_is_valid_but_not_real_evidence() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    plan_hash = validator.canonical_sha256(plan)

    assert (
        validator.validate_manifest(
            manifest,
            plan,
            plan_hash,
            source="api-gateway-example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_manifest(
        manifest,
        plan,
        plan_hash,
        source="api-gateway-example",
        real_evidence=True,
    )
    _assert_invalid(errors, "real API gateway evidence must set example_only=false")


def test_real_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _real_manifest_from_example()
    run_dir = REPO_ROOT / "reports" / "api-gateway-perf" / "test-gateway-20260526"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "evidence_manifest.json"
    adjusted = copy.deepcopy(manifest)
    adjusted["run_id"] = "test-gateway-20260526"
    for key, value in adjusted["artifacts"].items():
        adjusted["artifacts"][key] = value.replace(
            "example-api-gateway-20260526", "test-gateway-20260526"
        )
    path.write_text(json.dumps(adjusted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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


def test_manifest_rejects_artifact_path_traversal_wrong_extensions_and_wrong_prefix() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["artifacts"]["locust_report"] = "reports/api-gateway-perf/other-run/../report.txt"
    manifest["artifacts"]["grafana_dashboard"] = (
        "reports/api-gateway-perf/example-api-gateway-20260526/grafana.html"
    )

    errors = validator.validate_manifest(
        manifest,
        plan,
        validator.canonical_sha256(plan),
        source="api-gateway",
        real_evidence=False,
    )

    _assert_invalid(errors, "must not traverse")
    _assert_invalid(
        errors,
        "must stay under reports/api-gateway-perf/example-api-gateway-20260526/",
    )
    _assert_invalid(errors, "Locust report must be .html or .json")
    _assert_invalid(errors, "Grafana dashboard must be .png")


def test_manifest_rejects_real_threshold_error_rate_duration_and_count_failures() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    manifest = _real_manifest_from_example()
    manifest["duration_seconds"] = 1799
    manifest["endpoint_results"][0]["locust_p95_ms"] = 200
    manifest["endpoint_results"][1]["prometheus_histogram_quantile_p95_ms"] = 200
    manifest["endpoint_results"][1]["http_error_rate"] = 0.02
    manifest["endpoint_results"][2]["success_count"] = 101
    manifest["endpoint_results"][2]["request_count"] = 100

    errors = validator.validate_manifest(
        manifest,
        plan,
        validator.canonical_sha256(plan),
        source="api-gateway-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "duration_seconds fails threshold")
    _assert_invalid(errors, "algorithms_public locust_p95_ms fails threshold")
    _assert_invalid(errors, "auth_api_keys prometheus_histogram_quantile_p95_ms fails threshold")
    _assert_invalid(errors, "auth_api_keys http_error_rate fails threshold")
    _assert_invalid(errors, "business_demo success_count exceeds request_count")


def test_manifest_rejects_endpoint_drift_duplicates_and_timeline_mismatch() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["duration_seconds"] = 1200
    manifest["ended_utc"] = "2026-05-26T10:30:00Z"
    manifest["endpoint_results"][0]["path"] = "/v1/algorithms?debug=true"
    manifest["endpoint_results"][1]["endpoint_class"] = "algorithms_public"
    manifest["endpoint_results"][2]["endpoint_class"] = "extra_endpoint"

    errors = validator.validate_manifest(
        manifest,
        plan,
        validator.canonical_sha256(plan),
        source="api-gateway",
        real_evidence=False,
    )

    _assert_invalid(errors, "endpoint classes must match plan exactly")
    _assert_invalid(errors, "algorithms_public path must match plan")
    _assert_invalid(errors, "duration_seconds must match timestamps")


def test_manifest_rejects_cross_story_pass_claims_and_wrong_plan_hash() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["plan_sha256"] = "0" * 64
    manifest["chat_load_pass"] = True
    manifest["endpoint_results"][0]["hard_gate_pass"] = True

    errors = validator.validate_manifest(
        manifest,
        plan,
        validator.canonical_sha256(plan),
        source="api-gateway",
        real_evidence=False,
    )

    _assert_invalid(errors, "plan_sha256 does not match")
    _assert_invalid(errors, "API gateway evidence cannot claim unrelated pass status")


def test_evidence_path_mode_rejects_chat_directories() -> None:
    validator = _load_validator()

    assert (
        validator.validate_evidence_path_mode(
            Path("reports/api-gateway-perf/run-123/evidence_manifest.json")
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/chat-load/run-123/evidence_manifest.json")
        ),
        "API gateway evidence path must be",
    )


def test_locustfile_contract_imports_without_locust_and_builds_request_specs() -> None:
    validator = _load_validator()
    locustfile = _load_locustfile()

    assert validator.validate_locustfile() == []
    plan = locustfile.load_plan()
    assert locustfile.request_interval_seconds(plan) > 0
    public_spec = locustfile.build_request_spec(plan["endpoints"][0], {"API_GATEWAY_PERF_JWT": ""})
    assert public_spec["method"] == "GET"
    assert public_spec["path"] == "/v1/algorithms"
    auth_spec = locustfile.build_request_spec(
        plan["endpoints"][1], {"API_GATEWAY_PERF_JWT": "redacted-runtime-jwt"}
    )
    assert auth_spec["headers"]["Authorization"] == "Bearer redacted-runtime-jwt"


def test_locustfile_requires_jwt_only_for_authenticated_endpoint() -> None:
    locustfile = _load_locustfile()
    plan = locustfile.load_plan()

    assert not hasattr(locustfile.ApiGatewayPerfUser, "endpoints")
    assert locustfile.build_request_spec(plan["endpoints"][0], {})["headers"] == {}
    try:
        locustfile.build_request_spec(plan["endpoints"][1], {})
    except ValueError as exc:
        assert "API_GATEWAY_PERF_JWT" in str(exc)
    else:
        raise AssertionError("auth_api_keys endpoint should require API_GATEWAY_PERF_JWT")
