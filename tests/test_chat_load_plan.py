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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_chat_load_plan.py"
PROMPTS_PATH = REPO_ROOT / "tools" / "chat_load" / "prompts_v1.json"
PROFILES_PATH = REPO_ROOT / "tools" / "chat_load" / "staging_profiles.json"
EXAMPLE_MANIFEST_PATH = REPO_ROOT / "tools" / "chat_load" / "evidence_manifest.example.json"
SINGLE_NODE_PROFILES_PATH = REPO_ROOT / "tools" / "chat_load" / "single_node_profiles.json"
SINGLE_NODE_EXAMPLE_MANIFEST_PATH = (
    REPO_ROOT / "tools" / "chat_load" / "single_node_evidence_manifest.example.json"
)
INCIDENT_FALLBACK_PLAN_PATH = REPO_ROOT / "tools" / "chat_load" / "incident_fallback_plan.json"
INCIDENT_FALLBACK_EXAMPLE_MANIFEST_PATH = (
    REPO_ROOT / "tools" / "chat_load" / "incident_fallback_evidence_manifest.example.json"
)
G6_VALIDATION_PATH = REPO_ROOT / "tools" / "chat_load" / "g6_chat_latency_validation.json"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_chat_load_plan", VALIDATOR_PATH)
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


def test_committed_chat_load_plan_validates_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "chat load plan OK" in result.stdout


def test_prompt_fixture_has_exact_count_ids_categories_and_solve_coverage() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)

    assert validator.validate_prompts(prompts) == []
    assert prompts["prompt_count"] == 100
    assert [prompt["id"] for prompt in prompts["prompts"]] == [
        f"chat-load-v1-{index:03d}" for index in range(1, 101)
    ]
    categories = {prompt["category"] for prompt in prompts["prompts"]}
    assert categories == validator.REQUIRED_CATEGORIES
    solve_count = sum(
        1 for prompt in prompts["prompts"] if prompt["expected_path"] == "solve_expected"
    )
    assert solve_count >= 30


def test_prompt_missing_record_is_rejected() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    prompts["prompts"] = prompts["prompts"][:-1]

    errors = validator.validate_prompts(prompts)

    _assert_invalid(errors, "exactly 100 prompts")
    _assert_invalid(errors, "prompt IDs must be contiguous")


def test_prompt_secret_like_text_is_rejected() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    prompts["prompts"][0]["prompt"] = "Use bearer sk-example1234567890SECRET in this request"

    errors = validator.validate_prompts(prompts)

    _assert_invalid(errors, "forbidden bearer token")


def test_profiles_pin_prompt_hash_and_rps_math() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(PROFILES_PATH)
    expected_hash = validator.prompt_fixture_hash(prompts)

    assert validator.validate_profiles(profiles, expected_hash) == []


def test_baseline_source_math_drift_is_rejected() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(PROFILES_PATH)
    profiles["profiles"]["baseline"]["effective_requests_per_user_per_minute"] = 1

    errors = validator.validate_profiles(profiles, validator.prompt_fixture_hash(prompts))

    _assert_invalid(errors, "effective_requests_per_user_per_minute must be 3")
    _assert_invalid(errors, "RPS math does not match target_rps")


def test_profile_prompt_hash_drift_is_rejected() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(PROFILES_PATH)
    profiles["profiles"]["stress"]["prompt_fixture_sha256"] = "0" * 64

    errors = validator.validate_profiles(profiles, validator.prompt_fixture_hash(prompts))

    _assert_invalid(errors, "prompt_fixture_sha256 does not match")


def test_locustfile_static_contract_exposes_metric_helpers() -> None:
    validator = _load_validator()

    assert validator.validate_locustfile() == []


def test_example_manifest_is_valid_but_not_real_evidence() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    expected_hash = validator.prompt_fixture_hash(prompts)

    assert (
        validator.validate_manifest(
            manifest,
            expected_hash,
            source="example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_manifest(
        manifest,
        expected_hash,
        source="example",
        real_evidence=True,
    )
    _assert_invalid(errors, "real evidence must set example_only=false")


def test_real_evidence_path_mode_accepts_redacted_manifest(tmp_path: Path) -> None:
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["example_only"] = False
    run_dir = REPO_ROOT / "reports" / "chat-load" / "test-run-20260526"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "evidence_manifest.json"
    adjusted = copy.deepcopy(manifest)
    adjusted["run_id"] = "test-run-20260526"
    for profile in adjusted["profiles"].values():
        profile["locust_report"] = profile["locust_report"].replace(
            "example-run-20260526", "test-run-20260526"
        )
        profile["grafana_screenshot"] = profile["grafana_screenshot"].replace(
            "example-run-20260526", "test-run-20260526"
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


def test_real_evidence_threshold_failures_are_rejected() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(PROFILES_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["example_only"] = False
    manifest["profiles"]["baseline"]["metrics"]["first_token_p95_ms"] = 2000
    manifest["profiles"]["stress"]["metrics"]["streaming_tokens_per_second"] = 19.9
    manifest["profiles"]["soak"]["metrics"]["oom_count"] = 1

    errors = validator.validate_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        source="real",
        real_evidence=True,
        profiles_config=profiles["profiles"],
        hard_gate_config=profiles["hard_gate_thresholds"],
    )

    _assert_invalid(errors, "baseline first_token_p95_ms fails threshold")
    _assert_invalid(errors, "stress streaming_tokens_per_second fails threshold")
    _assert_invalid(errors, "soak oom_count fails threshold")


def test_real_evidence_hard_gate_failures_are_rejected_even_without_profile_threshold() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(PROFILES_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["example_only"] = False
    manifest["profiles"]["soak"]["metrics"]["first_token_p95_ms"] = 3000
    manifest["profiles"]["soak"]["metrics"]["e2e_solve_p95_ms"] = 90001

    errors = validator.validate_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        source="real",
        real_evidence=True,
        profiles_config=profiles["profiles"],
        hard_gate_config=profiles["hard_gate_thresholds"],
    )

    _assert_invalid(errors, "soak hard-gate first_token_p95_ms fails")
    _assert_invalid(errors, "soak hard-gate e2e_solve_p95_ms fails")


def test_evidence_rejects_path_traversal_and_wrong_run_id() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["profiles"]["baseline"]["locust_report"] = (
        "reports/chat-load/other-run/../baseline-locust.html"
    )

    errors = validator.validate_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        source="example",
        real_evidence=False,
    )

    _assert_invalid(errors, "must not traverse")
    _assert_invalid(errors, "must stay under reports/chat-load/example-run-20260526/")


def test_evidence_rejects_wrong_artifact_extension_even_when_name_is_generic() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["profiles"]["baseline"]["grafana_screenshot"] = (
        "reports/chat-load/example-run-20260526/baseline-dashboard.html"
    )
    manifest["profiles"]["stress"]["locust_report"] = (
        "reports/chat-load/example-run-20260526/stress-report.png"
    )

    errors = validator.validate_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        source="example",
        real_evidence=False,
    )

    _assert_invalid(errors, "Grafana screenshot must be .png")
    _assert_invalid(errors, "Locust report must be .html or .json")


def test_evidence_rejects_e2e_claim_without_solve_prompts() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["profiles"]["stress"]["metrics"]["solve_prompt_count"] = 0

    errors = validator.validate_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        source="example",
        real_evidence=False,
    )

    _assert_invalid(errors, "cannot claim E2E solve P95")


def test_schema_pins_required_profiles_and_metrics() -> None:
    validator = _load_validator()
    schema = _load_json(REPO_ROOT / "tools" / "chat_load" / "evidence_manifest.schema.json")

    assert validator.validate_schema(schema) == []


def test_single_node_profiles_pin_prompt_hash_rps_and_advisory_flags() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(SINGLE_NODE_PROFILES_PATH)

    assert (
        validator.validate_single_node_profiles(profiles, validator.prompt_fixture_hash(prompts))
        == []
    )


def test_single_node_profile_rps_drift_is_rejected() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(SINGLE_NODE_PROFILES_PATH)
    profiles["profiles"]["single_node_baseline"]["effective_requests_per_user_per_minute"] = 3

    errors = validator.validate_single_node_profiles(
        profiles, validator.prompt_fixture_hash(prompts)
    )

    _assert_invalid(errors, "effective_requests_per_user_per_minute must be 6")
    _assert_invalid(errors, "RPS math does not match target_rps")


def test_single_node_profile_rejects_hard_gate_candidate() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(SINGLE_NODE_PROFILES_PATH)
    profiles["profiles"]["single_node_baseline"]["hard_gate_candidate"] = True

    errors = validator.validate_single_node_profiles(
        profiles, validator.prompt_fixture_hash(prompts)
    )

    _assert_invalid(errors, "hard_gate_candidate must be False")


def test_single_node_manifest_rejects_nested_hard_gate_claim() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    manifest = _load_json(SINGLE_NODE_EXAMPLE_MANIFEST_PATH)
    manifest["profiles"]["single_node_baseline"]["hard_gate_candidate"] = True
    manifest["profiles"]["single_node_baseline"]["metrics"]["hard_gate_pass"] = True

    errors = validator.validate_single_node_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        source="single-node",
        real_evidence=False,
    )

    _assert_invalid(errors, "cannot be a hard-gate candidate")
    _assert_invalid(errors, "cannot claim hard-gate pass")


def test_single_node_locustfile_reuses_staging_metric_helpers() -> None:
    validator = _load_validator()

    assert validator.validate_single_node_locustfile() == []


def test_single_node_schema_pins_profile_and_metrics() -> None:
    validator = _load_validator()
    schema = _load_json(
        REPO_ROOT / "tools" / "chat_load" / "single_node_evidence_manifest.schema.json"
    )

    assert validator.validate_single_node_schema(schema) == []
    assert schema["$defs"]["metricsSnapshotPath"]["pattern"].endswith("\\.json$")


def test_single_node_example_manifest_is_valid_but_not_real_evidence() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    manifest = _load_json(SINGLE_NODE_EXAMPLE_MANIFEST_PATH)
    expected_hash = validator.prompt_fixture_hash(prompts)

    assert (
        validator.validate_single_node_manifest(
            manifest,
            expected_hash,
            source="single-node-example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_single_node_manifest(
        manifest,
        expected_hash,
        source="single-node-example",
        real_evidence=True,
    )
    _assert_invalid(errors, "real single-node evidence must set example_only=false")


def test_single_node_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _load_json(SINGLE_NODE_EXAMPLE_MANIFEST_PATH)
    manifest["example_only"] = False
    run_dir = REPO_ROOT / "reports" / "chat-single-node" / "test-single-node-20260526"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "evidence_manifest.json"
    adjusted = copy.deepcopy(manifest)
    adjusted["run_id"] = "test-single-node-20260526"
    profile = adjusted["profiles"]["single_node_baseline"]
    profile["locust_report"] = profile["locust_report"].replace(
        "example-single-node-20260526", "test-single-node-20260526"
    )
    profile["metrics_snapshot"] = profile["metrics_snapshot"].replace(
        "example-single-node-20260526", "test-single-node-20260526"
    )
    path.write_text(json.dumps(adjusted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--single-node-evidence", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )

    try:
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        path.unlink(missing_ok=True)
        run_dir.rmdir()


def test_single_node_evidence_rejects_wrong_node_count_and_environment() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    manifest = _load_json(SINGLE_NODE_EXAMPLE_MANIFEST_PATH)
    manifest["node_count"] = 5
    manifest["environment"] = "staging"

    errors = validator.validate_single_node_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        source="single-node",
        real_evidence=False,
    )

    _assert_invalid(errors, "node_count must be 1")
    _assert_invalid(errors, "environment must be single-node-dev")


def test_single_node_evidence_rejects_path_traversal_and_wrong_extensions() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    manifest = _load_json(SINGLE_NODE_EXAMPLE_MANIFEST_PATH)
    profile = manifest["profiles"]["single_node_baseline"]
    profile["locust_report"] = "reports/chat-single-node/other-run/../single-node.txt"
    profile["metrics_snapshot"] = (
        "reports/chat-single-node/example-single-node-20260526/single-node-metrics.html"
    )

    errors = validator.validate_single_node_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        source="single-node",
        real_evidence=False,
    )

    _assert_invalid(errors, "must not traverse")
    _assert_invalid(
        errors, "must stay under reports/chat-single-node/example-single-node-20260526/"
    )
    _assert_invalid(errors, "Locust report must be .html or .json")
    _assert_invalid(errors, "metrics snapshot must be .json")


def test_single_node_real_evidence_advisory_threshold_failures_are_rejected() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(SINGLE_NODE_PROFILES_PATH)
    manifest = _load_json(SINGLE_NODE_EXAMPLE_MANIFEST_PATH)
    manifest["example_only"] = False
    metrics = manifest["profiles"]["single_node_baseline"]["metrics"]
    metrics["first_token_p95_ms"] = 3000
    metrics["streaming_tokens_per_second"] = 19.9
    metrics["sandbox_startup_p95_ms"] = 100

    errors = validator.validate_single_node_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        source="single-node-real",
        real_evidence=True,
        profile_config=profiles["profiles"]["single_node_baseline"],
    )

    _assert_invalid(errors, "first_token_p95_ms fails advisory threshold")
    _assert_invalid(errors, "streaming_tokens_per_second fails advisory threshold")
    _assert_invalid(errors, "sandbox_startup_p95_ms fails advisory threshold")


def test_incident_fallback_plan_pins_providers_thresholds_and_prompt_hash() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    plan = _load_json(INCIDENT_FALLBACK_PLAN_PATH)

    assert (
        validator.validate_incident_fallback_plan(plan, validator.prompt_fixture_hash(prompts))
        == []
    )


def test_g6_chat_latency_validation_contract_pins_hard_gate_boundary() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(PROFILES_PATH)
    contract = _load_json(G6_VALIDATION_PATH)

    assert (
        validator.validate_g6_chat_latency_validation(
            contract,
            expected_hash=validator.prompt_fixture_hash(prompts),
            profiles_config=profiles,
        )
        == []
    )


def test_g6_chat_latency_validation_rejects_false_pass_claims() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(PROFILES_PATH)
    contract = _load_json(G6_VALIDATION_PATH)
    contract["hard_gate_pass"] = True
    contract["nested"] = {"staging_pass": True, "passed": True}
    contract["g6_status"] = "passed"

    errors = validator.validate_g6_chat_latency_validation(
        contract,
        expected_hash=validator.prompt_fixture_hash(prompts),
        profiles_config=profiles,
    )

    _assert_invalid(errors, "hard_gate_pass must be False")
    _assert_invalid(errors, "g6_status must be requires_real_staging_evidence")
    _assert_invalid(errors, "cannot claim G6 hard-gate or staging pass")


def test_g6_chat_latency_validation_rejects_wrong_unlock_source() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(PROFILES_PATH)
    contract = _load_json(G6_VALIDATION_PATH)
    contract["required_evidence_manifest"] = (
        "reports/chat-single-node/<run_id>/evidence_manifest.json"
    )
    contract["blocked_unlock_sources"] = ["example_manifest"]
    contract["blocked_unlock_conditions"] = ["docs-only"]
    contract["nested_manifest"] = {"example_only": True}

    errors = validator.validate_g6_chat_latency_validation(
        contract,
        expected_hash=validator.prompt_fixture_hash(prompts),
        profiles_config=profiles,
    )

    _assert_invalid(errors, "required_evidence_manifest must be reports/chat-load")
    _assert_invalid(errors, "blocked_unlock_sources must include")
    _assert_invalid(errors, "blocked_unlock_conditions must include example_only=true")
    _assert_invalid(errors, "cannot use example_only=true evidence")


def test_g6_chat_latency_validation_rejects_profile_or_blocker_order_drift() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(PROFILES_PATH)
    contract = _load_json(G6_VALIDATION_PATH)
    contract["required_profiles"] = ["baseline", "stress", "stress"]
    contract["blocked_unlock_sources"] = [
        "reports/chat-single-node/**",
        "tools/chat_load/evidence_manifest.example.json",
        "reports/chat-incident-fallback/**",
        "docs-only-checklist",
    ]

    errors = validator.validate_g6_chat_latency_validation(
        contract,
        expected_hash=validator.prompt_fixture_hash(prompts),
        profiles_config=profiles,
    )

    _assert_invalid(errors, "required_profiles must be baseline/stress/soak")
    _assert_invalid(errors, "blocked_unlock_sources must include")


def test_g6_chat_latency_validation_rejects_threshold_prompt_and_stress_drift() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    profiles = _load_json(PROFILES_PATH)
    contract = _load_json(G6_VALIDATION_PATH)
    contract["prompt_fixture_sha256"] = "0" * 64
    contract["hard_gate_thresholds"]["first_token_p95_max_ms"] = 2999
    contract["stress_profile"]["users"] = 99
    contract["stress_profile"]["target_rps"] = 99
    contract["stress_profile"]["run_time_seconds"] = 1799

    errors = validator.validate_g6_chat_latency_validation(
        contract,
        expected_hash=validator.prompt_fixture_hash(prompts),
        profiles_config=profiles,
    )

    _assert_invalid(errors, "prompt_fixture_sha256 does not match")
    _assert_invalid(errors, "hard_gate_thresholds.first_token_p95_max_ms must be 3000")
    _assert_invalid(errors, "stress_profile.users must match staging profile")
    _assert_invalid(errors, "stress_profile.target_rps must match staging profile")
    _assert_invalid(errors, "stress_profile.run_time_seconds must match staging profile")


def test_incident_fallback_plan_provider_and_threshold_drift_is_rejected() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    plan = _load_json(INCIDENT_FALLBACK_PLAN_PATH)
    plan["primary_provider"] = "qwen-max"
    plan["fallback_first_token_p95_max_ms"] = 3000
    plan["fallback_route_ratio_min"] = 0.95

    errors = validator.validate_incident_fallback_plan(plan, validator.prompt_fixture_hash(prompts))

    _assert_invalid(errors, "primary_provider must be deepseek-v3.5")
    _assert_invalid(errors, "fallback_first_token_p95_max_ms must be 5000")
    _assert_invalid(errors, "fallback_route_ratio_min must be 1.0")


def test_incident_fallback_schema_pins_artifacts_timeline_and_metrics() -> None:
    validator = _load_validator()
    schema = _load_json(
        REPO_ROOT / "tools" / "chat_load" / "incident_fallback_evidence_manifest.schema.json"
    )

    assert validator.validate_incident_fallback_schema(schema) == []
    assert "(?!.*\\.\\.)" in schema["$defs"]["locustReportPath"]["pattern"]
    assert "(?!.*\\.\\.)" in schema["$defs"]["jsonArtifactPath"]["pattern"]


def test_incident_fallback_example_manifest_is_valid_but_not_real_evidence() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    plan = _load_json(INCIDENT_FALLBACK_PLAN_PATH)
    manifest = _load_json(INCIDENT_FALLBACK_EXAMPLE_MANIFEST_PATH)
    expected_hash = validator.prompt_fixture_hash(prompts)
    plan_hash = validator.canonical_sha256(plan)

    assert (
        validator.validate_incident_fallback_manifest(
            manifest,
            expected_hash,
            plan_hash,
            source="incident-example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_incident_fallback_manifest(
        manifest,
        expected_hash,
        plan_hash,
        source="incident-example",
        real_evidence=True,
        plan_config=plan,
    )
    _assert_invalid(errors, "real incident fallback evidence must set example_only=false")


def test_incident_fallback_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _load_json(INCIDENT_FALLBACK_EXAMPLE_MANIFEST_PATH)
    manifest["example_only"] = False
    run_dir = REPO_ROOT / "reports" / "chat-incident-fallback" / "test-incident-20260526"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "evidence_manifest.json"
    adjusted = copy.deepcopy(manifest)
    adjusted["run_id"] = "test-incident-20260526"
    for key, value in adjusted["artifacts"].items():
        adjusted["artifacts"][key] = value.replace(
            "example-incident-fallback-20260526", "test-incident-20260526"
        )
    path.write_text(json.dumps(adjusted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--incident-fallback-evidence", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )

    try:
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        path.unlink(missing_ok=True)
        run_dir.rmdir()


def test_incident_fallback_manifest_rejects_path_traversal_and_wrong_extensions() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    plan = _load_json(INCIDENT_FALLBACK_PLAN_PATH)
    manifest = _load_json(INCIDENT_FALLBACK_EXAMPLE_MANIFEST_PATH)
    manifest["artifacts"]["locust_report"] = (
        "reports/chat-incident-fallback/other-run/../incident.txt"
    )
    manifest["artifacts"]["provider_health_snapshot"] = (
        "reports/chat-incident-fallback/example-incident-fallback-20260526/provider-health.html"
    )

    errors = validator.validate_incident_fallback_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        validator.canonical_sha256(plan),
        source="incident",
        real_evidence=False,
    )

    _assert_invalid(errors, "must not traverse")
    _assert_invalid(
        errors,
        "must stay under reports/chat-incident-fallback/example-incident-fallback-20260526/",
    )
    _assert_invalid(errors, "Locust report must be .html or .json")
    _assert_invalid(errors, "provider_health_snapshot must be .json")


def test_incident_fallback_real_evidence_threshold_failures_are_rejected() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    plan = _load_json(INCIDENT_FALLBACK_PLAN_PATH)
    manifest = _load_json(INCIDENT_FALLBACK_EXAMPLE_MANIFEST_PATH)
    manifest["example_only"] = False
    metrics = manifest["metrics"]
    metrics["switch_duration_seconds"] = 301
    metrics["fallback_first_token_p95_ms"] = 5000
    metrics["fallback_route_ratio"] = 0.99
    metrics["schema_parity_pass_count"] = 99
    metrics["fallback_provider_error_count"] = 1

    errors = validator.validate_incident_fallback_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        validator.canonical_sha256(plan),
        source="incident-real",
        real_evidence=True,
        plan_config=plan,
    )

    _assert_invalid(errors, "switch_duration_seconds fails threshold")
    _assert_invalid(errors, "fallback_first_token_p95_ms fails threshold")
    _assert_invalid(errors, "fallback_route_ratio fails threshold")
    _assert_invalid(errors, "schema parity counts must match")
    _assert_invalid(errors, "fallback_provider_error_count must be 0")


def test_incident_fallback_manifest_rejects_invalid_timeline_order_and_hard_gate_claims() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    plan = _load_json(INCIDENT_FALLBACK_PLAN_PATH)
    manifest = _load_json(INCIDENT_FALLBACK_EXAMPLE_MANIFEST_PATH)
    manifest["timeline"]["fallback_confirmed_utc"] = "2026-05-26T10:01:00Z"
    manifest["timeline"]["operator_decision_utc"] = "2026-05-26T10:03:00Z"
    manifest["timeline"]["measurement_ended_utc"] = "2026-05-26T10:06:00Z"
    manifest["timeline"]["measurement_started_utc"] = "2026-05-26T10:08:00Z"
    manifest["hard_gate_pass"] = True
    manifest["metrics"]["staging_pass"] = True

    errors = validator.validate_incident_fallback_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        validator.canonical_sha256(plan),
        source="incident",
        real_evidence=False,
    )

    _assert_invalid(errors, "fallback_confirmed_utc must be after operator_decision_utc")
    _assert_invalid(errors, "measurement_ended_utc must be after measurement_started_utc")
    _assert_invalid(errors, "incident fallback evidence cannot claim hard-gate or staging pass")


def test_incident_fallback_manifest_rejects_timeline_metric_mismatch() -> None:
    validator = _load_validator()
    prompts = _load_json(PROMPTS_PATH)
    plan = _load_json(INCIDENT_FALLBACK_PLAN_PATH)
    manifest = _load_json(INCIDENT_FALLBACK_EXAMPLE_MANIFEST_PATH)
    manifest["metrics"]["switch_duration_seconds"] = 179
    manifest["metrics"]["detection_window_seconds"] = 299

    errors = validator.validate_incident_fallback_manifest(
        manifest,
        validator.prompt_fixture_hash(prompts),
        validator.canonical_sha256(plan),
        source="incident",
        real_evidence=False,
    )

    _assert_invalid(errors, "switch_duration_seconds must match timeline")
    _assert_invalid(errors, "detection_window_seconds must match timeline")


def test_evidence_path_modes_remain_separate() -> None:
    validator = _load_validator()

    assert (
        validator.validate_evidence_path_mode(
            Path("reports/chat-load/run-123/evidence_manifest.json"), "staging"
        )
        == []
    )
    assert (
        validator.validate_evidence_path_mode(
            Path("reports/chat-single-node/run-123/evidence_manifest.json"), "single-node"
        )
        == []
    )
    assert (
        validator.validate_evidence_path_mode(
            Path("reports/chat-incident-fallback/run-123/evidence_manifest.json"),
            "incident-fallback",
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/chat-load/run-123/evidence_manifest.json"), "incident-fallback"
        ),
        "incident fallback evidence path must be",
    )
