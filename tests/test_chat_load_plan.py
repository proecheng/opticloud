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
