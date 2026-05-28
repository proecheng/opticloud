"""Validate Story 3.12 J3 SRE incident Tier 3 contract assets.

The validator is static by default. It validates future redacted operator
evidence only when an explicit manifest is passed with --evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
INCIDENT_DIR = REPO_ROOT / "tools" / "incidents"
CONTRACT_PATH = INCIDENT_DIR / "j3_sre_incident_contract.json"
SCHEMA_PATH = INCIDENT_DIR / "j3_sre_incident.schema.json"
EXAMPLE_MANIFEST_PATH = INCIDENT_DIR / "j3_sre_incident.example.json"
M3_6C_PLAN_PATH = REPO_ROOT / "tools" / "chat_load" / "incident_fallback_plan.json"

TIMELINE_FIELDS = {
    "incident_started_utc",
    "provider_health_failed_utc",
    "p0_declared_utc",
    "sre_paged_utc",
    "fallback_decision_utc",
    "fallback_confirmed_utc",
    "status_page_published_utc",
    "postmortem_due_utc",
}
MANIFEST_ROOT_REQUIRED = {
    "source_story",
    "contract_version",
    "incident_id",
    "example_only",
    "generated_by",
    "commit_sha",
    "environment",
    "severity",
    "trigger",
    "providers",
    "timeline",
    "provider_health_snapshot",
    "fallback_reference",
    "status_page_announcement",
    "postmortem_skeleton",
}
POSTMORTEM_SECTIONS = {
    "what_happened",
    "timeline",
    "impact",
    "detection",
    "mitigation",
    "root_cause_placeholder",
    "follow_ups",
    "compensation_placeholder",
}
STATUS_VOCABULARY = ["investigating", "identified", "monitoring", "resolved"]
FAKE_COMPLETION_FLAGS = {
    "status_page_publicly_available",
    "subscriber_webhook_sent",
    "dingtalk_webhook_called",
    "credits_refunded",
    "postmortem_publicly_published",
}
SENSITIVE_KEY_EXACT = {
    "authorization",
    "token",
    "auth_token",
    "bearer_token",
    "api_token",
    "access_token",
    "refresh_token",
    "session_token",
    "cookie",
    "session",
    "password",
    "secret",
    "api_key",
    "private_key",
    "access_key",
    "tenant_id",
    "customer_id",
    "user_id",
    "prompt",
    "provider_payload",
    "provider_request",
    "provider_response",
    "internal_hostname",
}
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"tenant[_-]?id|customer[_-]?id|user[_-]?id|cookie|prompt|provider[_-]?payload|"
    r"provider[_-]?request|provider[_-]?response|internal[_-]?hostname)([_-]|$)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_PATTERNS = {
    "bearer token": re.compile(r"bearer\s+[a-z0-9._~+/=-]{12,}", re.IGNORECASE),
    "api key assignment": re.compile(
        r"(api[_-]?key|token|secret)\s*[:=]\s*[a-z0-9._~+/=-]{12,}", re.IGNORECASE
    ),
    "generic sk key": re.compile(r"\bsk-[a-zA-Z0-9]{16,}\b"),
    "URL scheme": re.compile(r"https?://", re.IGNORECASE),
    "credentialed url": re.compile(r"https?://[^/\s:@]+:[^/\s:@]+@"),
    "Windows absolute path": re.compile(r"^[A-Za-z]:[\\/]"),
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(data: Any) -> str:
    return sha256(canonical_json_bytes(data)).hexdigest()


def _normalize_key(key: Any) -> str:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).lower()
    return normalized.replace("-", "_")


def _walk_values(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    values = [(path, value)]
    if isinstance(value, dict):
        for key, nested in value.items():
            values.extend(_walk_values(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            values.extend(_walk_values(nested, f"{path}[{index}]"))
    return values


def validate_no_sensitive_values(data: Any, source: str) -> list[str]:
    errors: list[str] = []
    for path, value in _walk_values(data):
        if isinstance(value, dict):
            for key in value:
                normalized_key = _normalize_key(key)
                if normalized_key in SENSITIVE_KEY_EXACT or SENSITIVE_KEY_PATTERN.search(str(key)):
                    errors.append(f"{source} contains forbidden sensitive key at {path}.{key}")
        if isinstance(value, str):
            if path == "$.$schema":
                continue
            for label, pattern in SENSITIVE_VALUE_PATTERNS.items():
                if pattern.search(value):
                    errors.append(f"{source} contains forbidden {label} at {path}")
    return errors


def _schema_required(schema: dict[str, Any], path: list[str]) -> set[str]:
    node: Any = schema
    for segment in path:
        node = node[segment]
    required = node.get("required")
    return set(required) if isinstance(required, list) else set()


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _path_safety_errors(path_value: str, incident_id: str, source: str) -> list[str]:
    errors: list[str] = []
    if "://" in path_value:
        errors.append(f"{source} path must not be a URL: {path_value}")
    if path_value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", path_value):
        errors.append(f"{source} path must be repository-relative: {path_value}")
    normalized = Path(path_value)
    if ".." in normalized.parts:
        errors.append(f"{source} path must not traverse directories: {path_value}")
    required_prefix = f"reports/j3-sre-incident/{incident_id}/"
    if not path_value.startswith(required_prefix):
        errors.append(f"{source} path must stay under {required_prefix}: {path_value}")
    if Path(path_value).suffix.lower() != ".json":
        errors.append(f"{source} path must be .json: {path_value}")
    return errors


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_values: dict[str, Any] = {
        "contract_version": "j3_sre_incident_tier3_v1",
        "source_story": "3.12",
        "journey": "J3",
        "persona": "wang-zhe-sre",
        "severity": "P0",
        "incident_type": "provider_outage",
        "primary_provider": "deepseek-v3.5",
        "fallback_provider": "qwen-max",
        "trigger": "provider_health_deepseek_failure",
        "alert_seconds_max": 30,
        "status_page_publish_seconds_max": 60,
        "postmortem_publish_hours_max": 24,
    }
    for key, expected in expected_values.items():
        if contract.get(key) != expected:
            errors.append(f"j3_sre_incident_contract.json {key} must be {expected}")
    if contract.get("status_vocabulary") != STATUS_VOCABULARY:
        errors.append("j3_sre_incident_contract.json status_vocabulary drifted")
    fallback_plan = contract.get("fallback_plan")
    m3_6c_plan = load_json(M3_6C_PLAN_PATH)
    expected_hash = canonical_sha256(m3_6c_plan)
    if not isinstance(fallback_plan, dict):
        errors.append("j3_sre_incident_contract.json fallback_plan must be an object")
    else:
        if fallback_plan.get("path") != "tools/chat_load/incident_fallback_plan.json":
            errors.append("j3_sre_incident_contract.json fallback_plan.path must be M3.6c plan")
        if fallback_plan.get("source_story") != "M3.6c":
            errors.append("j3_sre_incident_contract.json fallback_plan.source_story must be M3.6c")
        if fallback_plan.get("sha256") != expected_hash:
            errors.append("j3_sre_incident_contract.json fallback_plan.sha256 does not match")
    errors.extend(validate_no_sensitive_values(contract, "j3_sre_incident_contract.json"))
    return errors


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != MANIFEST_ROOT_REQUIRED:
        errors.append("J3 incident schema root required fields drifted")
    timeline_required = _schema_required(schema, ["$defs", "timeline"])
    if timeline_required != TIMELINE_FIELDS:
        errors.append("J3 incident schema timeline fields drifted")
    postmortem_required = _schema_required(
        schema, ["$defs", "postmortem", "properties", "sections"]
    )
    if postmortem_required != POSTMORTEM_SECTIONS:
        errors.append("J3 incident schema postmortem sections drifted")
    status_enum = schema.get("$defs", {}).get("status", {}).get("enum")
    if status_enum != STATUS_VOCABULARY:
        errors.append("J3 incident schema status vocabulary drifted")
    artifact_pattern = schema["$defs"]["providerHealth"]["properties"]["artifact_path"]["pattern"]
    if "reports/j3-sre-incident" not in artifact_pattern:
        errors.append("J3 incident schema artifact path must restrict reports/j3-sre-incident")
    if "(?!.*\\.\\.)" not in artifact_pattern:
        errors.append("J3 incident schema artifact path must reject traversal")
    errors.extend(validate_no_sensitive_values(schema, "j3_sre_incident.schema.json"))
    return errors


def _validate_fake_completion_claims(manifest: dict[str, Any], source: str) -> list[str]:
    errors: list[str] = []
    prefix = "example manifest" if manifest.get("example_only") is True else "manifest"
    for path, value in _walk_values(manifest):
        key = path.rsplit(".", maxsplit=1)[-1]
        if key in FAKE_COMPLETION_FLAGS and value is True:
            errors.append(f"{source} {prefix} cannot claim {key}")
    return errors


def validate_evidence_path_mode(path: Path, incident_id: str) -> list[str]:
    relative = path.as_posix()
    expected = "reports/j3-sre-incident/"
    if not relative.startswith(expected) or not relative.endswith("/incident_manifest.json"):
        return [
            "J3 incident evidence path must be "
            "reports/j3-sre-incident/<incident_id>/incident_manifest.json"
        ]
    parts = Path(relative).parts
    if len(parts) < 4 or parts[2] != incident_id:
        return ["J3 incident evidence path directory must match incident_id"]
    return []


def validate_manifest(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    incident_id = manifest.get("incident_id")
    if not isinstance(incident_id, str):
        return [f"{source} incident_id must be a string"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", incident_id):
        errors.append(f"{source} incident_id must be a stable slug")
    missing = MANIFEST_ROOT_REQUIRED - set(manifest)
    for key in sorted(missing):
        errors.append(f"{source} missing required field {key}")
    commit_sha = manifest.get("commit_sha")
    if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{7,40}", commit_sha):
        errors.append(f"{source} commit_sha must be 7-40 lowercase hex chars")
    if manifest.get("source_story") != "3.12":
        errors.append(f"{source} source_story must be 3.12")
    if manifest.get("contract_version") != contract.get("contract_version"):
        errors.append(f"{source} contract_version must match contract")
    if manifest.get("severity") != "P0":
        errors.append(f"{source} severity must be P0")
    if manifest.get("trigger") != contract.get("trigger"):
        errors.append(f"{source} trigger must match contract")

    example_only = manifest.get("example_only")
    if real_evidence and example_only is not False:
        errors.append(f"{source} real J3 incident evidence must set example_only=false")
    if not real_evidence and example_only is not True:
        errors.append(f"{source} example J3 incident manifest must set example_only=true")
    expected_environment = "staging-incident-drill" if real_evidence else "tier3-static-example"
    if manifest.get("environment") != expected_environment:
        errors.append(f"{source} environment must be {expected_environment}")

    providers = manifest.get("providers")
    if not isinstance(providers, dict):
        errors.append(f"{source} providers must be an object")
    else:
        if providers.get("primary_provider") != contract.get("primary_provider"):
            errors.append(f"{source} providers.primary_provider must match contract")
        if providers.get("fallback_provider") != contract.get("fallback_provider"):
            errors.append(f"{source} providers.fallback_provider must match contract")

    fallback_reference = manifest.get("fallback_reference")
    fallback_plan = contract.get("fallback_plan") if isinstance(contract, dict) else None
    if not isinstance(fallback_reference, dict) or not isinstance(fallback_plan, dict):
        errors.append(f"{source} fallback_reference must be an object")
    else:
        for key in ("source_story", "plan_path", "plan_sha256", "evidence_mode"):
            if key not in fallback_reference:
                errors.append(f"{source} fallback_reference missing field {key}")
        if fallback_reference.get("plan_path") != fallback_plan.get("path"):
            errors.append(
                f"{source} fallback_reference.plan_path must be {fallback_plan.get('path')}"
            )
        if fallback_reference.get("plan_sha256") != fallback_plan.get("sha256"):
            errors.append(f"{source} fallback_reference.plan_sha256 does not match")
        if fallback_reference.get("source_story") != "M3.6c":
            errors.append(f"{source} fallback_reference.source_story must be M3.6c")

    timeline = manifest.get("timeline")
    timeline_values: dict[str, Any] = timeline if isinstance(timeline, dict) else {}
    parsed: dict[str, datetime] = {}
    if not isinstance(timeline, dict):
        errors.append(f"{source} timeline must be an object")
    else:
        if set(timeline) != TIMELINE_FIELDS:
            errors.append(f"{source} timeline fields drifted")
        for key in TIMELINE_FIELDS:
            parsed_time = _parse_utc_timestamp(timeline.get(key))
            if parsed_time is None:
                errors.append(f"{source} {key} must be valid UTC timestamp")
            else:
                parsed[key] = parsed_time
        if set(parsed) == TIMELINE_FIELDS:
            if parsed["provider_health_failed_utc"] < parsed["incident_started_utc"]:
                errors.append(
                    f"{source} provider_health_failed_utc must not precede incident_started_utc"
                )
            if parsed["sre_paged_utc"] < parsed["provider_health_failed_utc"]:
                errors.append(f"{source} sre_paged_utc must not precede provider_health_failed_utc")
            if parsed["fallback_confirmed_utc"] <= parsed["fallback_decision_utc"]:
                errors.append(
                    f"{source} fallback_confirmed_utc must be after fallback_decision_utc"
                )
            status_delta = (
                parsed["status_page_published_utc"] - parsed["p0_declared_utc"]
            ).total_seconds()
            if status_delta < 0:
                errors.append(
                    f"{source} status_page_published_utc must not precede p0_declared_utc"
                )
            if status_delta > float(contract.get("status_page_publish_seconds_max", 60)):
                errors.append(f"{source} status_page_published_utc exceeds 60 second SLA")
            expected_due = parsed["p0_declared_utc"] + timedelta(
                hours=float(contract.get("postmortem_publish_hours_max", 24))
            )
            if parsed["postmortem_due_utc"] != expected_due:
                errors.append(
                    f"{source} postmortem_due_utc must be exactly 24h after p0_declared_utc"
                )

    provider_health = manifest.get("provider_health_snapshot")
    if not isinstance(provider_health, dict):
        errors.append(f"{source} provider_health_snapshot must be an object")
    else:
        for key in ("component", "observed_status", "artifact_path", "summary"):
            if key not in provider_health:
                errors.append(f"{source} provider_health_snapshot missing field {key}")
        if provider_health.get("component") != "llm-provider-deepseek":
            errors.append(
                f"{source} provider_health_snapshot.component must be llm-provider-deepseek"
            )
        if provider_health.get("observed_status") != "failed":
            errors.append(f"{source} provider_health_snapshot.observed_status must be failed")
        artifact_path = provider_health.get("artifact_path")
        if not isinstance(artifact_path, str):
            errors.append(f"{source} provider_health_snapshot.artifact_path must be a string")
        else:
            errors.extend(
                _path_safety_errors(
                    artifact_path,
                    incident_id,
                    f"{source} provider_health_snapshot.artifact_path",
                )
            )

    status_page = manifest.get("status_page_announcement")
    if not isinstance(status_page, dict):
        errors.append(f"{source} status_page_announcement must be an object")
    else:
        for key in (
            "status",
            "component",
            "started_at_utc",
            "published_at_utc",
            "public_summary",
            "affected_scope",
            "customer_visible",
            "next_update_due_utc",
        ):
            if key not in status_page:
                errors.append(f"{source} status_page_announcement missing field {key}")
        if status_page.get("status") != "investigating":
            errors.append(f"{source} status_page_announcement.status must be investigating")
        if status_page.get("component") != "llm-provider-deepseek":
            errors.append(
                f"{source} status_page_announcement.component must be llm-provider-deepseek"
            )
        if status_page.get("published_at_utc") != timeline_values.get(
            "status_page_published_utc", None
        ):
            errors.append(f"{source} status page published_at_utc must match timeline")
        if status_page.get("started_at_utc") != timeline_values.get("incident_started_utc", None):
            errors.append(f"{source} status page started_at_utc must match timeline")

    postmortem = manifest.get("postmortem_skeleton")
    if not isinstance(postmortem, dict):
        errors.append(f"{source} postmortem_skeleton must be an object")
    else:
        expected_url = f"/status/incidents/{incident_id}"
        if postmortem.get("public_url_path") != expected_url:
            errors.append(f"{source} public_url_path must match incident_id")
        if postmortem.get("publish_due_utc") != timeline_values.get("postmortem_due_utc", None):
            errors.append(f"{source} postmortem publish_due_utc must match timeline")
        sections = postmortem.get("sections")
        if not isinstance(sections, dict):
            errors.append(f"{source} postmortem sections must be an object")
        else:
            missing_sections = POSTMORTEM_SECTIONS - set(sections)
            for key in sorted(missing_sections):
                errors.append(f"{source} postmortem missing section {key}")
            section_timeline = sections.get("timeline")
            if not isinstance(section_timeline, list) or set(section_timeline) != TIMELINE_FIELDS:
                errors.append(
                    f"{source} postmortem timeline must reference canonical timeline fields"
                )

    errors.extend(_validate_fake_completion_claims(manifest, source))
    errors.extend(validate_no_sensitive_values(manifest, source))
    return errors


def _repo_relative(path: Path, flag: str, errors: list[str]) -> Path:
    try:
        return Path(path.resolve().relative_to(REPO_ROOT.resolve()).as_posix())
    except ValueError:
        errors.append(f"{flag} path must be inside the repository")
        return Path(path.as_posix())


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    example_manifest = load_json(EXAMPLE_MANIFEST_PATH)
    if not isinstance(contract, dict):
        return ["j3_sre_incident_contract.json must contain an object"]
    errors.extend(validate_contract(contract))
    if not isinstance(schema, dict):
        errors.append("j3_sre_incident.schema.json must contain an object")
    else:
        errors.extend(validate_schema(schema))
    if not isinstance(example_manifest, dict):
        errors.append("j3_sre_incident.example.json must contain an object")
    else:
        errors.extend(
            validate_manifest(
                example_manifest,
                contract,
                source="j3_sre_incident.example.json",
                real_evidence=False,
            )
        )
    if evidence_path is not None:
        evidence = load_json(evidence_path)
        if not isinstance(evidence, dict):
            errors.append(f"{evidence_path} must contain an object")
        else:
            relative = _repo_relative(evidence_path, "--evidence", errors)
            incident_id = evidence.get("incident_id")
            if isinstance(incident_id, str):
                errors.extend(validate_evidence_path_mode(relative, incident_id))
            else:
                errors.append(f"{relative.as_posix()} incident_id must be a string")
            errors.extend(
                validate_manifest(
                    evidence,
                    contract,
                    source=relative.as_posix(),
                    real_evidence=True,
                )
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Optional redacted incident manifest under reports/j3-sre-incident/<incident_id>/",
    )
    args = parser.parse_args(argv)

    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("j3 incident contract OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
