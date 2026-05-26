"""Validate M3.7 sandbox security audit static assets."""

from __future__ import annotations

import argparse
import json
import re
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SECURITY_DIR = REPO_ROOT / "infra" / "sandbox-security"
PLAN_PATH = SECURITY_DIR / "audit_plan.json"
SCENARIOS_PATH = SECURITY_DIR / "attack_scenarios.json"
SUPPLY_CHAIN_POLICY_PATH = SECURITY_DIR / "supply_chain_policy.json"
HARDENING_MANIFEST_PATH = SECURITY_DIR / "k8s" / "sandbox-runner-hardening.yaml"
APPARMOR_PROFILE_PATH = SECURITY_DIR / "apparmor" / "sandbox-runner.apparmor"
EVIDENCE_SCHEMA_PATH = SECURITY_DIR / "pentest_evidence.schema.json"
EVIDENCE_EXAMPLE_PATH = SECURITY_DIR / "pentest_evidence.example.json"

ESCAPE_IDS = (
    "escape-fork-bomb",
    "escape-root-filesystem-write",
    "escape-external-network-egress",
    "escape-docker-socket-access",
    "escape-sys-ptrace",
    "escape-mount-namespace",
    "escape-host-path-mount",
    "escape-privileged-container",
    "escape-host-namespaces",
    "escape-capability-escalation",
    "escape-kernel-module-load",
    "escape-proc-host-inspection",
)
SUPPLY_CHAIN_IDS = (
    "supply-chain-typosquat-pypi",
    "supply-chain-poisoned-base-image",
    "supply-chain-sbom-diff-hijack",
)
EXPECTED_IDS = (*ESCAPE_IDS, *SUPPLY_CHAIN_IDS)
VALIDATED_GUARDS = {
    "apparmor_profile",
    "capability_drop_all",
    "deny_all_egress",
    "gvisor_runtime_class",
    "no_docker_socket",
    "no_host_path",
    "no_host_namespaces",
    "read_only_root_filesystem",
    "seccomp_runtime_default",
    "supply_chain_policy",
}
EVIDENCE_REQUIRED = {
    "source_story",
    "example_only",
    "run_id",
    "reviewer_type",
    "reviewed_scenario_id",
    "audit_plan_sha256",
    "attack_scenarios_sha256",
    "supply_chain_policy_sha256",
    "hardening_manifest_sha256",
    "apparmor_profile_sha256",
    "redaction_reviewed",
    "artifact_paths",
    "finding_summary_redacted",
}
FORBIDDEN_PASS_CLAIMS = {
    "sandbox_security_pass",
    "p0_escape_zero_quarterly",
    "gvisor_escape_impossible",
}
FORBIDDEN_METADATA_PATTERNS = {
    r":\s*\(\)\s*\{": "shell fork bomb payload",
    r"\bmount\s+-": "mount command",
    r"\bdocker\s+(run|exec|build|pull)\b": "Docker command",
    r"\bnsenter\b": "host namespace probe command",
    r"\bmodprobe\b": "kernel module load command",
    r"\binsmod\b": "kernel module insert command",
    r"\brm\s+-rf\b": "destructive shell command",
    r"\b(curl|wget)\s+https?://": "network fetch command",
    r"\bcat\s+/etc/(shadow|passwd)\b": "credential probe command",
    r"\b(production|prod)\.[A-Za-z0-9.-]+": "production hostname",
    r"\b(password|api[_-]?key|secret|token)\s*[:=]": "credential-like material",
    r"\.\./\.\.": "host traversal payload",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def canonical_sha256(data: Any) -> str:
    return sha256(canonical_json_bytes(data)).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _object_field_errors(
    data: dict[str, Any], *, required: set[str], allowed: set[str], source: str
) -> list[str]:
    errors: list[str] = []
    for key in sorted(required - set(data)):
        errors.append(f"{source} missing required field {key}")
    for key in sorted(set(data) - allowed):
        errors.append(f"{source} unexpected field {key}")
    return errors


def _iter_text_values(data: Any, prefix: str) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            values.extend(_iter_text_values(value, f"{prefix}.{key}"))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            values.extend(_iter_text_values(value, f"{prefix}[{index}]"))
    elif isinstance(data, str):
        values.append((prefix, data))
    return values


def validate_metadata_safety(data: Any, *, source: str) -> list[str]:
    errors: list[str] = []
    for field, value in _iter_text_values(data, source):
        for pattern, description in FORBIDDEN_METADATA_PATTERNS.items():
            if re.search(pattern, value, flags=re.IGNORECASE):
                errors.append(f"{field} contains forbidden {description}")
    return errors


def validate_plan(plan: dict[str, Any], scenarios: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_metadata_safety(plan, source="audit_plan.json"))
    expected = {
        "audit_version": "sandbox_security_audit_v1",
        "source_story": "M3.7",
        "source_decision": "PMR3",
        "source_gap": "CRG6",
    }
    for key, value in expected.items():
        if plan.get(key) != value:
            errors.append(f"audit_plan.json {key} must be {value}")
    if plan.get("scenario_ids") != list(EXPECTED_IDS):
        errors.append("audit_plan.json scenario_ids must match canonical M3.7 scenario order")
    scenario_ids = [
        scenario.get("scenario_id")
        for scenario in scenarios.get("scenarios", [])
        if isinstance(scenario, dict)
    ]
    if plan.get("scenario_ids") != scenario_ids:
        errors.append("audit_plan.json scenario_ids must match attack_scenarios.json order")
    coverage = plan.get("guard_coverage")
    if not isinstance(coverage, dict):
        errors.append("audit_plan.json guard_coverage must be an object")
    else:
        if set(coverage) != VALIDATED_GUARDS:
            errors.append("audit_plan.json guard_coverage must cover every validated guard")
        for guard, rule in coverage.items():
            if guard not in VALIDATED_GUARDS or not isinstance(rule, str) or not rule:
                errors.append(f"audit_plan.json guard {guard} has no validator coverage")
    return errors


def validate_scenarios(scenarios: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_metadata_safety(scenarios, source="attack_scenarios.json"))
    items = scenarios.get("scenarios")
    if not isinstance(items, list):
        return ["attack_scenarios.json scenarios must be a list"]
    if len(items) != 15:
        errors.append("attack_scenarios.json must define exactly 15 scenarios")
    ids: list[str] = []
    for scenario in items:
        if not isinstance(scenario, dict):
            errors.append("attack_scenarios.json scenario must be an object")
            continue
        required = {
            "scenario_id",
            "category",
            "attack_vector",
            "expected_guard",
            "expected_result",
            "automation_mode",
        }
        errors.extend(
            _object_field_errors(
                scenario,
                required=required,
                allowed=required,
                source="attack_scenarios.json scenario",
            )
        )
        scenario_id = scenario.get("scenario_id")
        category = scenario.get("category")
        ids.append(str(scenario_id))
        if scenario_id in ESCAPE_IDS and not str(scenario_id).startswith("escape-"):
            errors.append("container escape scenario_id must start with escape-")
        if category == "container_escape" and not str(scenario_id).startswith("escape-"):
            errors.append("container escape scenario_id must start with escape-")
        if category == "supply_chain" and not str(scenario_id).startswith("supply-chain-"):
            errors.append("supply chain scenario_id must start with supply-chain-")
        if scenario.get("expected_guard") not in VALIDATED_GUARDS:
            errors.append(f"{scenario_id} unknown expected_guard")
        if scenario.get("expected_result") != "blocked":
            errors.append(f"{scenario_id} expected_result must be blocked")
        if scenario.get("automation_mode") != "metadata_static":
            errors.append(f"{scenario_id} automation_mode must be metadata_static")
    if len(ids) != len(set(ids)):
        errors.append("attack_scenarios.json scenario_id values must be unique")
    if ids != list(EXPECTED_IDS):
        errors.append("attack_scenarios.json scenarios must match canonical M3.7 IDs")
    if plan.get("scenario_ids") != ids:
        errors.append("attack_scenarios.json scenarios must match audit_plan.json scenario_ids")
    return errors


def validate_supply_chain_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "policy_version",
        "source_story",
        "allowed_dependencies",
        "denied_typosquat_patterns",
        "allowed_base_image_digests",
        "allowed_sbom_added_packages",
        "example_candidate",
    }
    errors.extend(
        _object_field_errors(
            policy,
            required=required,
            allowed=required,
            source="supply_chain_policy.json",
        )
    )
    if policy.get("policy_version") != "sandbox_supply_chain_policy_v1":
        errors.append("supply_chain_policy.json policy_version drifted")
    candidate = policy.get("example_candidate")
    if isinstance(candidate, dict):
        errors.extend(validate_supply_chain_candidate(candidate, policy))
    else:
        errors.append("supply_chain_policy.json example_candidate must be an object")
    return errors


def validate_supply_chain_candidate(candidate: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    dependencies = candidate.get("dependencies")
    if not isinstance(dependencies, list):
        errors.append("candidate dependencies must be a list")
        dependencies = []
    denied = set(policy.get("denied_typosquat_patterns", []))
    allowed = set(policy.get("allowed_dependencies", []))
    for dependency in dependencies:
        if dependency in denied:
            errors.append(f"denied typosquat dependency {dependency}")
        if dependency not in allowed:
            errors.append(f"dependency {dependency} is not allowed")
    if candidate.get("base_image_digest") not in set(policy.get("allowed_base_image_digests", [])):
        errors.append("base image digest is not allowed")
    allowed_added = set(policy.get("allowed_sbom_added_packages", []))
    for package in candidate.get("sbom_added_packages", []):
        if package not in allowed_added:
            errors.append(f"unexpected SBOM added package {package}")
    return errors


def validate_hardening_manifest(manifest_text: str) -> list[str]:
    errors: list[str] = []
    required_snippets = {
        "runtimeClassName: gvisor": "runtimeClassName must be gvisor",
        "allowPrivilegeEscalation: false": "allowPrivilegeEscalation must be false",
        "readOnlyRootFilesystem: true": "readOnlyRootFilesystem must be true",
        "runAsNonRoot: true": "runAsNonRoot must be true",
        "type: RuntimeDefault": "seccompProfile.type must be RuntimeDefault",
        "appArmorProfile:": "appArmorProfile must be configured",
        "kind: NetworkPolicy": "deny-all egress NetworkPolicy must be present",
        "egress: []": "deny-all egress NetworkPolicy must use egress: []",
    }
    for snippet, message in required_snippets.items():
        if snippet not in manifest_text:
            errors.append(message)
    forbidden_snippets = {
        "privileged: true": "privileged must not be true",
        "hostPID: true": "hostPID must not be true",
        "hostIPC: true": "hostIPC must not be true",
        "hostNetwork: true": "hostNetwork must not be true",
        "hostPath:": "hostPath volumes are forbidden",
        "/var/run/docker.sock": "Docker socket mount is forbidden",
    }
    for snippet, message in forbidden_snippets.items():
        if snippet in manifest_text:
            errors.append(message)
    if not re.search(r"\n\s+drop:\s*\n\s+- ALL(?:\s*\n|$)", manifest_text):
        errors.append("capabilities.drop must include ALL")
    if re.search(r"\n\s+add:\s*\n\s+-", manifest_text):
        errors.append("must not add Linux capabilities")
    if 'cpu: "1"' not in manifest_text or "memory: 1Gi" not in manifest_text:
        errors.append("sandbox resources must remain 1 vCPU and 1Gi memory")
    return errors


def validate_apparmor_profile(profile_text: str) -> list[str]:
    errors: list[str] = []
    for snippet in (
        "profile opticloud-sandbox-runner",
        "deny /** w",
        "deny /var/run/docker.sock rw",
        "deny network raw",
        "deny capability sys_admin",
        "deny capability sys_module",
        "deny capability sys_ptrace",
    ):
        if snippet not in profile_text:
            errors.append(f"AppArmor profile missing {snippet}")
    return errors


def validate_evidence_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = set(schema.get("required", []))
    if required != EVIDENCE_REQUIRED:
        errors.append("pentest evidence schema required fields drifted")
    if schema.get("additionalProperties") is not False:
        errors.append("pentest evidence schema must reject additional properties")
    return errors


def _artifact_path_errors(path_value: str, run_id: str) -> list[str]:
    errors: list[str] = []
    if path_value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", path_value):
        errors.append(f"artifact path must be repository-relative: {path_value}")
    if "://" in path_value:
        errors.append(f"artifact path must not be a URL: {path_value}")
    if ".." in Path(path_value).parts:
        errors.append(f"artifact path must not traverse directories: {path_value}")
    required_prefix = f"reports/sandbox-security/{run_id}/"
    if not path_value.startswith(required_prefix):
        errors.append(f"artifact path must stay under {required_prefix}: {path_value}")
    return errors


def validate_evidence_manifest(
    evidence: dict[str, Any],
    plan: dict[str, Any],
    scenarios: dict[str, Any],
    policy: dict[str, Any],
    *,
    real_evidence: bool,
    source: str,
) -> list[str]:
    errors: list[str] = []
    allowed = EVIDENCE_REQUIRED | FORBIDDEN_PASS_CLAIMS
    errors.extend(
        _object_field_errors(evidence, required=EVIDENCE_REQUIRED, allowed=allowed, source=source)
    )
    run_id = evidence.get("run_id")
    if not isinstance(run_id, str):
        return errors + [f"{source} run_id must be a string"]
    if evidence.get("source_story") != "M3.7":
        errors.append(f"{source} source_story must be M3.7")
    if evidence.get("example_only") is not (not real_evidence):
        expected = "false" if real_evidence else "true"
        errors.append(f"{source} example_only must be {expected}")
    if real_evidence and evidence.get("reviewer_type") != "third_party_pentester":
        errors.append(f"{source} real evidence reviewer_type must be third_party_pentester")
    if real_evidence and evidence.get("redaction_reviewed") is not True:
        errors.append(f"{source} real evidence must set redaction_reviewed=true")
    scenario_ids = set(plan.get("scenario_ids", []))
    if evidence.get("reviewed_scenario_id") not in scenario_ids:
        errors.append(f"{source} reviewed_scenario_id must be one of the 15 scenarios")
    expected_hashes = {
        "audit_plan_sha256": canonical_sha256(plan),
        "attack_scenarios_sha256": canonical_sha256(scenarios),
        "supply_chain_policy_sha256": canonical_sha256(policy),
        "hardening_manifest_sha256": file_sha256(HARDENING_MANIFEST_PATH),
        "apparmor_profile_sha256": file_sha256(APPARMOR_PROFILE_PATH),
    }
    for key, expected in expected_hashes.items():
        if evidence.get(key) != expected:
            errors.append(f"{source} {key} does not match")
    for claim in FORBIDDEN_PASS_CLAIMS:
        if evidence.get(claim):
            errors.append(f"{source} cannot claim {claim}")
    artifact_paths = evidence.get("artifact_paths")
    if not isinstance(artifact_paths, dict):
        errors.append(f"{source} artifact_paths must be an object")
    else:
        for value in artifact_paths.values():
            if isinstance(value, str):
                errors.extend(_artifact_path_errors(value, run_id))
            else:
                errors.append(f"{source} artifact path values must be strings")
    return errors


def validate_evidence_path_mode(path: Path) -> list[str]:
    relative = path.as_posix()
    if path.is_absolute():
        try:
            relative = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        except ValueError:
            return ["sandbox security evidence path must be inside the repository"]
    if not relative.startswith("reports/sandbox-security/") or not relative.endswith(
        "/pentest_evidence.json"
    ):
        return [
            "sandbox security evidence path must be "
            "reports/sandbox-security/<run_id>/pentest_evidence.json"
        ]
    return []


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    plan = load_json(PLAN_PATH)
    scenarios = load_json(SCENARIOS_PATH)
    policy = load_json(SUPPLY_CHAIN_POLICY_PATH)
    evidence_schema = load_json(EVIDENCE_SCHEMA_PATH)
    evidence_example = load_json(EVIDENCE_EXAMPLE_PATH)
    manifest_text = HARDENING_MANIFEST_PATH.read_text(encoding="utf-8")
    apparmor_text = APPARMOR_PROFILE_PATH.read_text(encoding="utf-8")

    errors.extend(validate_plan(plan, scenarios))
    errors.extend(validate_scenarios(scenarios, plan))
    errors.extend(validate_supply_chain_policy(policy))
    errors.extend(validate_hardening_manifest(manifest_text))
    errors.extend(validate_apparmor_profile(apparmor_text))
    errors.extend(validate_evidence_schema(evidence_schema))
    errors.extend(
        validate_evidence_manifest(
            evidence_example,
            plan,
            scenarios,
            policy,
            real_evidence=False,
            source="pentest_evidence.example.json",
        )
    )
    if evidence_path is not None:
        errors.extend(validate_evidence_path_mode(evidence_path))
        evidence = load_json(evidence_path)
        if isinstance(evidence, dict):
            errors.extend(
                validate_evidence_manifest(
                    evidence,
                    plan,
                    scenarios,
                    policy,
                    real_evidence=True,
                    source=evidence_path.as_posix(),
                )
            )
        else:
            errors.append(f"{evidence_path} must contain an object")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Optional real pentest evidence under reports/sandbox-security/<run_id>/",
    )
    args = parser.parse_args(argv)
    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("sandbox security audit OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
