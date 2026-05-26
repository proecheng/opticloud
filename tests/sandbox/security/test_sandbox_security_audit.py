from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_sandbox_security_audit.py"
SECURITY_DIR = REPO_ROOT / "infra" / "sandbox-security"
PLAN_PATH = SECURITY_DIR / "audit_plan.json"
SCENARIOS_PATH = SECURITY_DIR / "attack_scenarios.json"
SUPPLY_CHAIN_POLICY_PATH = SECURITY_DIR / "supply_chain_policy.json"
HARDENING_MANIFEST_PATH = SECURITY_DIR / "k8s" / "sandbox-runner-hardening.yaml"
APPARMOR_PROFILE_PATH = SECURITY_DIR / "apparmor" / "sandbox-runner.apparmor"
EVIDENCE_SCHEMA_PATH = SECURITY_DIR / "pentest_evidence.schema.json"
EVIDENCE_EXAMPLE_PATH = SECURITY_DIR / "pentest_evidence.example.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "sandbox-security-audit.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_sandbox_security_audit", VALIDATOR_PATH)
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


def _real_evidence_from_example() -> dict[str, Any]:
    validator = _load_validator()
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)
    evidence["example_only"] = False
    evidence["reviewer_type"] = "third_party_pentester"
    evidence["redaction_reviewed"] = True
    evidence["audit_plan_sha256"] = validator.canonical_sha256(_load_json(PLAN_PATH))
    evidence["attack_scenarios_sha256"] = validator.canonical_sha256(_load_json(SCENARIOS_PATH))
    evidence["supply_chain_policy_sha256"] = validator.canonical_sha256(
        _load_json(SUPPLY_CHAIN_POLICY_PATH)
    )
    evidence["hardening_manifest_sha256"] = validator.file_sha256(HARDENING_MANIFEST_PATH)
    evidence["apparmor_profile_sha256"] = validator.file_sha256(APPARMOR_PROFILE_PATH)
    return evidence


def test_committed_sandbox_security_audit_validates_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "sandbox security audit OK" in result.stdout


def test_audit_plan_pins_story_and_15_ordered_scenarios() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    scenarios = _load_json(SCENARIOS_PATH)

    assert validator.validate_plan(plan, scenarios) == []
    assert plan["audit_version"] == "sandbox_security_audit_v1"
    assert plan["source_story"] == "M3.7"
    assert plan["source_decision"] == "PMR3"
    assert plan["source_gap"] == "CRG6"
    assert len(plan["scenario_ids"]) == 15
    assert plan["scenario_ids"] == [scenario["scenario_id"] for scenario in scenarios["scenarios"]]


def test_audit_plan_rejects_exploit_hosts_and_credentials() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    scenarios = _load_json(SCENARIOS_PATH)
    plan["notes"] = [
        "curl https://production.opticloud.example/internal",
        "api_key=should-not-appear",
    ]

    errors = validator.validate_plan(plan, scenarios)

    _assert_invalid(errors, "forbidden network fetch command")
    _assert_invalid(errors, "forbidden production hostname")
    _assert_invalid(errors, "forbidden credential-like material")


def test_scenario_count_category_and_guard_drift_is_rejected() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    scenarios = _load_json(SCENARIOS_PATH)
    scenarios["scenarios"].pop()
    scenarios["scenarios"][0]["expected_guard"] = "unvalidated_guard"
    scenarios["scenarios"][1]["scenario_id"] = "wrong-prefix-001"

    errors = validator.validate_scenarios(scenarios, plan)

    _assert_invalid(errors, "must define exactly 15 scenarios")
    _assert_invalid(errors, "unknown expected_guard")
    _assert_invalid(errors, "container escape scenario_id must start with escape-")


def test_scenario_metadata_rejects_executable_exploit_payloads() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    scenarios = _load_json(SCENARIOS_PATH)
    scenarios["scenarios"][0]["attack_vector"] = ":(){ :|:& };:"
    scenarios["scenarios"][1]["attack_vector"] = "mount -t proc proc /host/proc"
    scenarios["scenarios"][2]["attack_vector"] = "docker run -v /var/run/docker.sock:/sock"
    scenarios["scenarios"][3]["attack_vector"] = "../../etc/shadow"

    errors = validator.validate_scenarios(scenarios, plan)

    _assert_invalid(errors, "forbidden shell fork bomb payload")
    _assert_invalid(errors, "forbidden mount command")
    _assert_invalid(errors, "forbidden Docker command")
    _assert_invalid(errors, "forbidden host traversal payload")


def test_supply_chain_policy_rejects_typosquat_image_and_sbom_drift() -> None:
    validator = _load_validator()
    policy = _load_json(SUPPLY_CHAIN_POLICY_PATH)
    candidate = copy.deepcopy(policy["example_candidate"])
    candidate["dependencies"].append("reqeusts")
    candidate["base_image_digest"] = "sha256:poisoned"
    candidate["sbom_added_packages"].append("curl")

    errors = validator.validate_supply_chain_candidate(candidate, policy)

    _assert_invalid(errors, "denied typosquat dependency")
    _assert_invalid(errors, "base image digest is not allowed")
    _assert_invalid(errors, "unexpected SBOM added package")


def test_hardening_manifest_and_apparmor_profile_are_valid() -> None:
    validator = _load_validator()
    manifest_text = HARDENING_MANIFEST_PATH.read_text(encoding="utf-8")
    apparmor_text = APPARMOR_PROFILE_PATH.read_text(encoding="utf-8")

    assert validator.validate_hardening_manifest(manifest_text) == []
    assert validator.validate_apparmor_profile(apparmor_text) == []
    assert "runtimeClassName: gvisor" in manifest_text
    assert "appArmorProfile" in manifest_text
    assert "capabilities:" in manifest_text
    assert "drop:" in manifest_text
    assert "ALL" in manifest_text


def test_hardening_manifest_rejects_privileged_hostpath_and_missing_runtime_guards() -> None:
    validator = _load_validator()
    manifest_text = HARDENING_MANIFEST_PATH.read_text(encoding="utf-8")
    mutated = (
        manifest_text.replace("runtimeClassName: gvisor", "runtimeClassName: runc")
        .replace("allowPrivilegeEscalation: false", "allowPrivilegeEscalation: true")
        .replace("readOnlyRootFilesystem: true", "readOnlyRootFilesystem: false")
        .replace("type: RuntimeDefault", "type: Unconfined")
        .replace("drop:\n                - ALL", "add:\n                - SYS_PTRACE")
    )
    mutated += "\n  hostPID: true\n  volumes:\n    - name: docker\n      hostPath:\n        path: /var/run/docker.sock\n"

    errors = validator.validate_hardening_manifest(mutated)

    _assert_invalid(errors, "runtimeClassName must be gvisor")
    _assert_invalid(errors, "allowPrivilegeEscalation must be false")
    _assert_invalid(errors, "readOnlyRootFilesystem must be true")
    _assert_invalid(errors, "seccompProfile.type must be RuntimeDefault")
    _assert_invalid(errors, "capabilities.drop must include ALL")
    _assert_invalid(errors, "must not add Linux capabilities")
    _assert_invalid(errors, "hostPID must not be true")
    _assert_invalid(errors, "hostPath volumes are forbidden")
    _assert_invalid(errors, "Docker socket mount is forbidden")


def test_evidence_schema_and_example_are_valid_static_examples() -> None:
    validator = _load_validator()
    schema = _load_json(EVIDENCE_SCHEMA_PATH)
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)
    plan = _load_json(PLAN_PATH)
    scenarios = _load_json(SCENARIOS_PATH)
    policy = _load_json(SUPPLY_CHAIN_POLICY_PATH)

    assert validator.validate_evidence_schema(schema) == []
    assert (
        validator.validate_evidence_manifest(
            evidence,
            plan,
            scenarios,
            policy,
            real_evidence=False,
            source="evidence-example",
        )
        == []
    )


def test_evidence_rejects_fake_pass_claims_and_hash_mismatch() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    scenarios = _load_json(SCENARIOS_PATH)
    policy = _load_json(SUPPLY_CHAIN_POLICY_PATH)
    evidence = _real_evidence_from_example()
    evidence["sandbox_security_pass"] = True
    evidence["audit_plan_sha256"] = "0" * 64
    evidence["artifact_paths"]["redacted_report"] = "/tmp/report.pdf"

    errors = validator.validate_evidence_manifest(
        evidence,
        plan,
        scenarios,
        policy,
        real_evidence=True,
        source="evidence-real",
    )

    _assert_invalid(errors, "cannot claim sandbox_security_pass")
    _assert_invalid(errors, "audit_plan_sha256 does not match")
    _assert_invalid(errors, "artifact path must be repository-relative")


def test_evidence_path_mode_accepts_real_evidence_with_sibling_safe_artifacts() -> None:
    evidence = _real_evidence_from_example()
    run_dir = REPO_ROOT / "reports" / "sandbox-security" / "test-pentest-20260526"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "pentest_evidence.json"
    evidence["run_id"] = "test-pentest-20260526"
    evidence["artifact_paths"] = {
        "redacted_report": "reports/sandbox-security/test-pentest-20260526/redacted-report.pdf",
        "redaction_audit": "reports/sandbox-security/test-pentest-20260526/redaction-audit.json",
    }
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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


def test_evidence_path_mode_rejects_wrong_report_directory(tmp_path: Path) -> None:
    validator = _load_validator()
    wrong_path = REPO_ROOT / "reports" / "prod-traffic-replay" / "run" / "pentest_evidence.json"

    _assert_invalid(
        validator.validate_evidence_path_mode(wrong_path),
        "sandbox security evidence path must be",
    )


def test_runbook_documents_static_boundary_and_failure_response() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert "CI is static/structural" in runbook
    assert "does not prove real gVisor" in runbook
    assert "third-party pentest" in runbook
    assert "redaction" in runbook
    assert "P0/P1 security investigation" in runbook
    assert "Do not commit generated reports" in runbook


def test_ci_wires_sandbox_security_filter_and_optional_evidence_validation() -> None:
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    for expected in (
        "sandbox_security_audit: ${{ steps.filter.outputs.sandbox_security_audit }}",
        "sandbox-security-audit-validation:",
        "'infra/sandbox-security/**'",
        "'scripts/validate_sandbox_security_audit.py'",
        "'tests/sandbox/security/**'",
        "'docs/runbooks/sandbox-security-audit.md'",
        "'reports/sandbox-security/**'",
        "uv run python scripts/validate_sandbox_security_audit.py --evidence",
        "uv run pytest tests/sandbox/security -v",
    ):
        assert expected in workflow
