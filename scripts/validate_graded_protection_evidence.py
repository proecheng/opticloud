"""Validate Story 9.8 graded protection evidence aggregation assets.

Default validation is static. Future redacted operator evidence is validated
only when passed explicitly with --evidence.
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "tools" / "graded_protection_evidence"
CONTRACT_PATH = EVIDENCE_DIR / "graded_protection_evidence_contract.json"
SCHEMA_PATH = EVIDENCE_DIR / "graded_protection_evidence_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = EVIDENCE_DIR / "graded_protection_evidence_manifest.example.json"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DASHBOARD_CONTRACT_PATH = (
    REPO_ROOT / "tools" / "governance_dashboard" / ("governance_dashboard_contract.json")
)

SOURCE_STORY = "9.8"
EVIDENCE_VERSION = "graded_protection_evidence_v1"
TARGET_LEVEL = "mlps_level_2"
REPORT_ROOT = "reports/graded-protection-evidence"
MANIFEST_FILENAME = "evidence_manifest.json"
REQUIRED_DOMAINS = (
    "system_scope",
    "asset_and_network_boundary",
    "identity_and_access_control",
    "security_audit_and_logging",
    "data_protection_and_backup",
    "vulnerability_and_incident_response",
    "operations_and_change_management",
    "legal_and_third_party_review",
    "timestamp_and_blockchain_preservation",
    "governance_dashboard_handoff",
)
REQUIRED_ARTIFACT_CLASSES = (
    "scope_statement",
    "asset_inventory_snapshot",
    "network_boundary_diagram_redacted",
    "access_control_matrix",
    "audit_log_retention_statement",
    "backup_restore_evidence",
    "vulnerability_scan_summary",
    "incident_drill_summary",
    "change_management_sample",
    "third_party_assessment_tracker",
    "legal_signoff_record",
    "tsa_timestamp_receipt",
    "blockchain_preservation_receipt",
    "finding_register",
    "dashboard_handoff_record",
)
PRESERVATION_PROVIDERS = ("tsa_rfc3161", "antchain", "tencent_zhixin_chain")
BLOCKCHAIN_PROVIDERS = {"antchain", "tencent_zhixin_chain"}
LEGAL_REVIEW_ROLES = ("Legal", "Compliance", "Security", "SRE")
GATE_STATUSES = ("green", "yellow", "red", "unknown", "not_run")
ARTIFACT_STATUSES = ("not_run_example", "present", "missing", "stale", "failed", "deferred")
LEGAL_REVIEW_STATUSES = ("not_run_example", "passed", "failed", "missing", "unknown")
RECEIPT_VERIFICATION_STATUSES = ("not_run_example", "passed", "failed", "missing", "unknown")
TRACK_MODES = ("standard_m5", "simplified_v1_5")
ALLOWED_EVIDENCE_MODES = ("contract_static", "redacted_manifest", "manual_review")
DISALLOWED_EVIDENCE_MODES = {
    "external_network",
    "tsa_api",
    "blockchain_api",
    "assessment_vendor_api",
    "legal_esign_api",
}
STOP_SHIP_SEVERITIES = {"P0", "P1", "P2"}
UNRESOLVED_FINDING_STATUSES = {"open", "in_progress", "deferred", "missing"}
GAP_DOMAIN_STATUSES = {"red", "yellow", "unknown"}
GAP_ARTIFACT_STATUSES = {"missing", "stale", "failed", "deferred"}
GAP_REVIEW_STATUSES = {"failed", "missing", "unknown"}
GAP_RECEIPT_STATUSES = {"failed", "missing", "unknown"}
MANIFEST_ROOT_REQUIRED = {
    "source_story",
    "evidence_version",
    "run_id",
    "example_only",
    "generated_by",
    "commit_sha",
    "track_mode",
    "period",
    "overall_gate_status",
    "domain_results",
    "artifact_results",
    "hash_manifest",
    "preservation_receipts",
    "legal_reviews",
    "findings",
    "dashboard_handoff",
    "redaction_reviewed",
    "release_approved",
    "real_assessment_institution_engaged",
    "real_public_security_filing_completed",
    "real_mlps_level_2_certificate_obtained",
    "real_tsa_timestamp_issued",
    "real_blockchain_preservation_completed",
    "real_legal_signoff_completed",
    "real_evidence_aggregation_completed",
    "certificate_artifact_id",
}
STATIC_COMPLETION_FLAGS = {
    "all_findings_resolved",
    "assessment_institution_engaged",
    "blockchain_preservation_completed",
    "external_ticket_created",
    "legal_signoff_completed",
    "mlps_level_2_certificate_obtained",
    "production_release_approved",
    "public_security_filing_completed",
    "real_assessment_institution_engaged",
    "real_blockchain_preservation_completed",
    "real_evidence_aggregation_completed",
    "real_external_ticket_created",
    "real_legal_signoff_completed",
    "real_mlps_level_2_certificate_obtained",
    "real_public_security_filing_completed",
    "real_tsa_timestamp_issued",
    "release_approved",
    "tsa_timestamp_issued",
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
    "tsa_credentials",
    "tsa_token",
    "tsa_api_key",
    "blockchain_api_credentials",
    "blockchain_token",
    "legal_signature_private_key",
    "tenant_id",
    "customer_id",
    "user_id",
    "account_id",
    "email",
    "phone",
    "prompt",
    "provider_payload",
    "provider_request",
    "provider_response",
    "raw_log",
    "raw_logs",
    "raw_screenshot",
    "raw_vulnerability_payload",
    "raw_network_map",
    "raw_metric_labels",
}
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"token|cookie|credential|tenant[_-]?id|customer[_-]?id|user[_-]?id|"
    r"account[_-]?id|email|phone|prompt|provider[_-]?payload|provider[_-]?request|"
    r"provider[_-]?response|raw[_-]?log|raw[_-]?screenshot|raw[_-]?vulnerability|"
    r"raw[_-]?network|raw[_-]?metric|customer[_-]?identifying|legal[_-]?signature|"
    r"tsa[_-]?(token|credential|api[_-]?key)|blockchain[_-]?(token|credential|api))([_-]|$)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_PATTERNS = {
    "email address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone number": re.compile(r"\b(?:\+?86|\+?1)?[-\s(]*\d{3}[-)\s]*\d{3,4}[-\s]*\d{4}\b"),
    "bearer token": re.compile(r"bearer\s+[a-z0-9._~+/=-]{12,}", re.IGNORECASE),
    "api key assignment": re.compile(
        r"(api[_-]?key|token|secret|tsa|blockchain)\s*[:=]\s*[a-z0-9._~+/=-]{12,}",
        re.IGNORECASE,
    ),
    "generic sk key": re.compile(r"\bsk-[a-zA-Z0-9]{16,}\b"),
    "credentialed URL": re.compile(r"https?://[^/\s:@]+:[^/\s:@]+@"),
    "production hostname": re.compile(r"https?://[^/\s]*opticloud\.cn", re.IGNORECASE),
    "Windows absolute path": re.compile(r"^[A-Za-z]:[\\/]"),
    "POSIX absolute path": re.compile(
        r"^/(?:tmp|home|users|var|etc|opt|mnt|root|workspace|volumes|private)(?:/|$)",
        re.IGNORECASE,
    ),
    "raw network map": re.compile(
        r"\b(raw_network_map|prod-vpc|10\.\d+\.\d+\.\d+/24)\b", re.IGNORECASE
    ),
    "raw vulnerability payload": re.compile(
        r"\b(raw_vulnerability_payload|nmap\s+-|sqlmap|metasploit|msfconsole)\b",
        re.IGNORECASE,
    ),
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


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
            if path.endswith(".$schema") or path.endswith(".$id"):
                continue
            for label, pattern in SENSITIVE_VALUE_PATTERNS.items():
                if pattern.search(value):
                    errors.append(f"{source} contains forbidden {label} at {path}")
            if ".." in Path(value).parts:
                errors.append(f"{source} contains forbidden directory traversal at {path}")
    return errors


def _schema_required(schema: dict[str, Any], path: list[str]) -> set[str]:
    node: Any = schema
    for segment in path:
        node = node[segment]
    required = node.get("required")
    return set(required) if isinstance(required, list) else set()


def _stable_slug(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", value) is not None


def _date(value: Any) -> bool:
    return (
        isinstance(value, str) and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value) is not None
    )


def _utc(value: Any) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value)
        is not None
    )


def _commit_sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{7,40}", value) is not None


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def discover_dashboard_state() -> dict[str, Any]:
    dashboard = load_json(DASHBOARD_CONTRACT_PATH)
    evidence = dashboard.get("evidence") if isinstance(dashboard, dict) else {}
    boundaries = dashboard.get("boundaries") if isinstance(dashboard, dict) else {}
    return {
        "source_story": dashboard.get("source_story"),
        "dashboard_version": dashboard.get("dashboard_version"),
        "dashboard_intent": dashboard.get("dashboard_intent"),
        "evidence_report_directory": evidence.get("report_directory")
        if isinstance(evidence, dict)
        else None,
        "manifest_filename": evidence.get("manifest_filename")
        if isinstance(evidence, dict)
        else None,
        "boundaries_false": sorted(
            key
            for key, value in (boundaries or {}).items()
            if isinstance(key, str) and value is False
        ),
    }


def _ids(items: Any, key: str) -> list[Any]:
    return [item.get(key) for item in items] if isinstance(items, list) else []


def _finding_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    findings = manifest.get("findings")
    if not isinstance(findings, list):
        return {}
    return {
        item.get("finding_id"): item
        for item in findings
        if isinstance(item, dict) and isinstance(item.get("finding_id"), str)
    }


def _finding_has_ticket(finding: dict[str, Any]) -> bool:
    tickets = finding.get("ticket_refs")
    if not isinstance(tickets, list) or not tickets:
        return False
    required = {"ticket_id", "owner", "severity", "due_date", "status"}
    return all(isinstance(ticket, dict) and required <= set(ticket) for ticket in tickets)


def _item_findings_valid(
    item: dict[str, Any], findings: dict[str, dict[str, Any]], label: str
) -> list[str]:
    ids = item.get("finding_ids")
    if not isinstance(ids, list) or not ids:
        return [f"{label} requires finding_ids"]
    errors: list[str] = []
    for finding_id in ids:
        finding = findings.get(finding_id)
        if finding is None:
            errors.append(f"{label} references unknown finding {finding_id}")
        elif not _finding_has_ticket(finding):
            errors.append(f"{label} finding {finding_id} must include ticket refs")
    return errors


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_no_sensitive_values(contract, "contract"))
    expected = {
        "source_story": SOURCE_STORY,
        "evidence_version": EVIDENCE_VERSION,
        "epic": 9,
        "target_level": TARGET_LEVEL,
        "cadence": "quarterly",
        "pipeline_intent": "offline_evidence_aggregation",
        "assessment_start_target": "M3",
        "certification_target": "M5",
        "standard_track_target": "M5",
        "simplified_track_target": "v1.5",
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            errors.append(f"contract {key} must be {value}")
    references = contract.get("external_references")
    if not isinstance(references, list) or len(references) != 3:
        errors.append("external_references must contain exactly three references")
    else:
        required_reference_fields = {
            "source_name",
            "reference_type",
            "url",
            "retrieved_at",
            "scope_note",
            "not_legal_advice",
        }
        for index, reference in enumerate(references):
            if not isinstance(reference, dict):
                errors.append(f"external reference {index} must be object")
                continue
            for field in required_reference_fields:
                if field not in reference:
                    errors.append(f"external reference missing {field}")
            if reference.get("not_legal_advice") is not True:
                errors.append("external reference must set not_legal_advice=true")
            if not _date(reference.get("retrieved_at")):
                errors.append("external reference retrieved_at must be YYYY-MM-DD")
    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("contract evidence must be object")
    else:
        if evidence.get("report_directory") != REPORT_ROOT:
            errors.append("contract evidence report_directory drifted")
        if evidence.get("manifest_filename") != MANIFEST_FILENAME:
            errors.append("contract evidence manifest_filename drifted")
    if contract.get("required_domains") != list(REQUIRED_DOMAINS):
        errors.append("required domains drifted")
    if contract.get("required_artifact_classes") != list(REQUIRED_ARTIFACT_CLASSES):
        errors.append("required artifact classes drifted")
    mapped_domains: list[Any] = []
    mapped_artifacts: set[str] = set()
    maps = contract.get("domain_artifact_map")
    if not isinstance(maps, list):
        errors.append("domain_artifact_map must be list")
    else:
        for item in maps:
            if not isinstance(item, dict):
                errors.append("domain_artifact_map item must be object")
                continue
            domain_id = item.get("domain_id")
            mapped_domains.append(domain_id)
            if domain_id not in REQUIRED_DOMAINS:
                errors.append(f"domain_artifact_map maps invalid domain {domain_id}")
            artifacts = item.get("artifact_classes")
            if not isinstance(artifacts, list) or not artifacts:
                errors.append(f"domain_artifact_map {domain_id} must map artifact_classes")
                continue
            for artifact_class in artifacts:
                if artifact_class not in REQUIRED_ARTIFACT_CLASSES:
                    errors.append(f"domain_artifact_map {domain_id} maps invalid artifact class")
                else:
                    mapped_artifacts.add(artifact_class)
    if mapped_domains != list(REQUIRED_DOMAINS):
        errors.append("domain_artifact_map domains must match required domains")
    if mapped_artifacts != set(REQUIRED_ARTIFACT_CLASSES):
        errors.append("domain_artifact_map must cover every required artifact class")
    providers = contract.get("preservation_provider_options")
    if _ids(providers, "provider") != list(PRESERVATION_PROVIDERS):
        errors.append("preservation provider options drifted")
    else:
        for provider in providers:
            if provider.get("external_call_in_scope") is not False:
                errors.append("preservation providers must set external_call_in_scope=false")
    if contract.get("legal_review_roles") != list(LEGAL_REVIEW_ROLES):
        errors.append("legal review roles drifted")
    if contract.get("gate_statuses") != list(GATE_STATUSES):
        errors.append("gate statuses drifted")
    if contract.get("artifact_statuses") != list(ARTIFACT_STATUSES):
        errors.append("artifact statuses drifted")
    if contract.get("track_modes") != list(TRACK_MODES):
        errors.append("track modes drifted")
    if contract.get("allowed_evidence_modes") != list(ALLOWED_EVIDENCE_MODES):
        errors.append("allowed evidence modes drifted")
    if set(contract.get("disallowed_evidence_modes", [])) != DISALLOWED_EVIDENCE_MODES:
        errors.append("disallowed evidence modes drifted")
    if contract.get("observed_dashboard_state") != discover_dashboard_state():
        errors.append("observed_dashboard_state drifted")
    boundaries = contract.get("boundaries")
    if not isinstance(boundaries, dict):
        errors.append("boundaries must be object")
    else:
        for claim in STATIC_COMPLETION_FLAGS:
            if claim in boundaries and boundaries[claim] is not False:
                errors.append(f"boundary {claim} must be false")
    if set(contract.get("disallowed_static_completion_claims", [])) != STATIC_COMPLETION_FLAGS:
        errors.append("disallowed_static_completion_claims drifted")
    return errors


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = set(schema.get("required", []))
    if required != MANIFEST_ROOT_REQUIRED:
        errors.append("schema required root fields drifted")
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        return errors + ["schema $defs missing"]
    expected_defs = {
        "domainId": REQUIRED_DOMAINS,
        "artifactClass": REQUIRED_ARTIFACT_CLASSES,
        "legalRole": LEGAL_REVIEW_ROLES,
        "gateStatus": GATE_STATUSES,
        "artifactStatus": ARTIFACT_STATUSES,
        "trackMode": TRACK_MODES,
        "evidenceMode": ALLOWED_EVIDENCE_MODES,
    }
    for key, expected in expected_defs.items():
        enum = defs.get(key, {}).get("enum") if isinstance(defs.get(key), dict) else None
        if enum != list(expected):
            errors.append(f"schema {key} enum drifted")
    return errors


def _validate_root_fields(manifest: dict[str, Any], source: str) -> list[str]:
    errors: list[str] = []
    missing = sorted(MANIFEST_ROOT_REQUIRED - set(manifest))
    if missing:
        errors.extend(f"{source} missing root field {field}" for field in missing)
    if manifest.get("source_story") != SOURCE_STORY:
        errors.append(f"{source} source_story must be {SOURCE_STORY}")
    if manifest.get("evidence_version") != EVIDENCE_VERSION:
        errors.append(f"{source} evidence_version must be {EVIDENCE_VERSION}")
    if not _stable_slug(manifest.get("run_id")):
        errors.append(f"{source} run_id must be stable slug")
    if not _commit_sha(manifest.get("commit_sha")):
        errors.append(f"{source} commit_sha must be 7-40 lowercase hex")
    if manifest.get("track_mode") not in TRACK_MODES:
        errors.append(f"{source} track_mode invalid")
    if manifest.get("overall_gate_status") not in GATE_STATUSES:
        errors.append(f"{source} overall_gate_status invalid")
    return errors


def _validate_static_flags(manifest: dict[str, Any], source: str, real_evidence: bool) -> list[str]:
    errors: list[str] = []
    if not real_evidence:
        for flag in STATIC_COMPLETION_FLAGS:
            if manifest.get(flag) is True:
                errors.append(f"{source} static example cannot claim {flag}")
    else:
        if manifest.get("example_only") is not False:
            errors.append(f"{source} example_only must be false")
        if manifest.get("redaction_reviewed") is not True:
            errors.append(f"{source} real evidence redaction_reviewed must be true")
        if manifest.get("real_evidence_aggregation_completed") is not True:
            errors.append(
                f"{source} real evidence real_evidence_aggregation_completed must be true"
            )
    return errors


def _validate_domain_results(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    source: str,
) -> list[str]:
    errors: list[str] = []
    domains = manifest.get("domain_results")
    if _ids(domains, "domain_id") != list(REQUIRED_DOMAINS):
        errors.append(f"{source} domain_results ids must match required domains")
        return errors
    contract_map = {
        item["domain_id"]: item["artifact_classes"]
        for item in contract.get("domain_artifact_map", [])
        if isinstance(item, dict)
    }
    for domain in domains:
        if not isinstance(domain, dict):
            errors.append(f"{source} domain_result must be object")
            continue
        domain_id = domain.get("domain_id")
        status = domain.get("status")
        if status not in (*GATE_STATUSES, "not_run_example"):
            errors.append(f"{source} domain {domain_id} status invalid")
        if domain.get("artifact_classes") != contract_map.get(domain_id):
            errors.append(f"{source} domain {domain_id} artifact_classes drifted")
        if status in GAP_DOMAIN_STATUSES:
            errors.extend(
                _item_findings_valid(
                    domain,
                    findings,
                    f"domain {domain_id} status {status}",
                )
            )
    return errors


def _validate_artifact_results(
    manifest: dict[str, Any], findings: dict[str, dict[str, Any]], source: str
) -> list[str]:
    errors: list[str] = []
    artifacts = manifest.get("artifact_results")
    if _ids(artifacts, "artifact_class") != list(REQUIRED_ARTIFACT_CLASSES):
        errors.append(f"{source} artifact_results classes must match required artifact classes")
        return errors
    seen_ids: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append(f"{source} artifact_result must be object")
            continue
        artifact_id = artifact.get("artifact_id")
        artifact_class = artifact.get("artifact_class")
        status = artifact.get("status")
        seen_ids.add(artifact_id)
        if not _stable_slug(artifact_id):
            errors.append(f"{source} artifact {artifact_id} id must be stable slug")
        if artifact_class not in REQUIRED_ARTIFACT_CLASSES:
            errors.append(f"{source} artifact {artifact_id} class invalid")
        if artifact.get("domain_id") not in REQUIRED_DOMAINS:
            errors.append(f"{source} artifact {artifact_id} domain invalid")
        if status not in ARTIFACT_STATUSES:
            errors.append(f"{source} artifact {artifact_id} status invalid")
        mode = artifact.get("evidence_mode")
        if mode not in ALLOWED_EVIDENCE_MODES:
            errors.append(f"{source} artifact {artifact_id} invalid evidence_mode")
        if mode in DISALLOWED_EVIDENCE_MODES:
            errors.append(f"{source} artifact {artifact_id} invalid evidence_mode")
        if status in GAP_ARTIFACT_STATUSES:
            errors.extend(
                _item_findings_valid(
                    artifact,
                    findings,
                    f"artifact {artifact_id} status {status}",
                )
            )
    if len(seen_ids) != len(REQUIRED_ARTIFACT_CLASSES):
        errors.append(f"{source} artifact ids must be unique")
    return errors


def _validate_hash_manifest(manifest: dict[str, Any], source: str) -> list[str]:
    errors: list[str] = []
    artifacts = [
        artifact
        for artifact in manifest.get("artifact_results", [])
        if isinstance(artifact, dict) and artifact.get("status") != "deferred"
    ]
    expected_ids = [artifact.get("artifact_id") for artifact in artifacts]
    hashes = manifest.get("hash_manifest")
    if not isinstance(hashes, list):
        return [f"{source} hash_manifest must be list"]
    actual_ids = [entry.get("artifact_id") for entry in hashes if isinstance(entry, dict)]
    if sorted(actual_ids) != sorted(expected_ids):
        errors.append(f"{source} hash_manifest artifact ids must match non-deferred artifacts")
    required_fields = {
        "artifact_id",
        "artifact_class",
        "artifact_path",
        "sha256",
        "generated_date",
        "retention_class",
        "evidence_mode",
    }
    artifact_by_id = {artifact.get("artifact_id"): artifact for artifact in artifacts}
    for entry in hashes:
        if not isinstance(entry, dict):
            errors.append(f"{source} hash_manifest entry must be object")
            continue
        missing = required_fields - set(entry)
        if missing:
            errors.append(f"{source} hash_manifest entry missing {sorted(missing)[0]}")
        if not _sha256(entry.get("sha256")):
            errors.append(f"{source} hash_manifest {entry.get('artifact_id')} sha256 invalid")
        if not _date(entry.get("generated_date")):
            errors.append(
                f"{source} hash_manifest {entry.get('artifact_id')} generated_date invalid"
            )
        if entry.get("evidence_mode") not in ALLOWED_EVIDENCE_MODES:
            errors.append(
                f"{source} hash_manifest {entry.get('artifact_id')} invalid evidence_mode"
            )
        artifact = artifact_by_id.get(entry.get("artifact_id"))
        if artifact and entry.get("artifact_class") != artifact.get("artifact_class"):
            errors.append(f"{source} hash_manifest {entry.get('artifact_id')} class drifted")
    return errors


def _validate_legal_reviews(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    reviews = manifest.get("legal_reviews")
    if _ids(reviews, "role") != list(LEGAL_REVIEW_ROLES):
        errors.append(f"{source} legal_reviews roles must match legal review roles")
        return errors
    for review in reviews:
        status = review.get("status")
        role = review.get("role")
        if status not in LEGAL_REVIEW_STATUSES:
            errors.append(f"{source} legal review {role} status invalid")
        if real_evidence and status != "passed":
            errors.append(f"{source} real evidence legal review {role} must pass")
        if status in GAP_REVIEW_STATUSES:
            errors.extend(_item_findings_valid(review, findings, f"legal review {role}"))
    if real_evidence and manifest.get("real_legal_signoff_completed") is not True:
        errors.append(f"{source} real evidence real_legal_signoff_completed must be true")
    return errors


def _validate_preservation_receipts(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    source: str,
) -> list[str]:
    errors: list[str] = []
    receipts = manifest.get("preservation_receipts")
    if not isinstance(receipts, list):
        return [f"{source} preservation_receipts must be list"]
    providers = [receipt.get("provider") for receipt in receipts if isinstance(receipt, dict)]
    for receipt in receipts:
        if not isinstance(receipt, dict):
            errors.append(f"{source} preservation receipt must be object")
            continue
        provider = receipt.get("provider")
        artifact_id = receipt.get("artifact_id")
        verification_status = receipt.get("verification_status")
        if provider not in PRESERVATION_PROVIDERS:
            errors.append(f"{source} preservation receipt provider invalid")
        if verification_status not in RECEIPT_VERIFICATION_STATUSES:
            errors.append(f"{source} preservation receipt {provider} verification_status invalid")
        if not _stable_slug(artifact_id):
            errors.append(f"{source} preservation receipt artifact_id invalid")
        if not _sha256(receipt.get("hash_sha256")):
            errors.append(f"{source} preservation receipt {provider} hash_sha256 invalid")
        if provider == "tsa_rfc3161":
            for field in (
                "timestamp_utc",
                "policy_oid_or_profile",
                "tsa_certificate_ref",
                "receipt_artifact_path",
                "verification_status",
            ):
                if field not in receipt:
                    errors.append(f"{source} TSA receipt missing {field}")
            if not _utc(receipt.get("timestamp_utc")):
                errors.append(f"{source} TSA receipt timestamp_utc invalid")
        if provider in BLOCKCHAIN_PROVIDERS:
            for field in (
                "chain_receipt_id",
                "preserved_at_utc",
                "receipt_artifact_path",
                "verification_status",
            ):
                if field not in receipt:
                    errors.append(f"{source} blockchain receipt missing {field}")
            if not _utc(receipt.get("preserved_at_utc")):
                errors.append(f"{source} blockchain receipt preserved_at_utc invalid")
        if receipt.get("verification_status") in GAP_RECEIPT_STATUSES:
            errors.extend(
                _item_findings_valid(
                    receipt,
                    findings,
                    f"preservation receipt {provider}",
                )
            )
    if manifest.get("real_tsa_timestamp_issued") is True and "tsa_rfc3161" not in providers:
        errors.append(f"{source} real TSA timestamp claim requires tsa_rfc3161 receipt")
    if manifest.get(
        "real_blockchain_preservation_completed"
    ) is True and not BLOCKCHAIN_PROVIDERS.intersection(providers):
        errors.append(
            f"{source} real blockchain preservation claim requires at least one selected blockchain receipt"
        )
    return errors


def _validate_dashboard_handoff(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    source: str,
) -> list[str]:
    errors: list[str] = []
    handoff = manifest.get("dashboard_handoff")
    if not isinstance(handoff, dict):
        return [f"{source} dashboard_handoff must be object"]
    dashboard_state = contract.get("observed_dashboard_state", {})
    if handoff.get("dashboard_version") != dashboard_state.get("dashboard_version"):
        errors.append(f"{source} dashboard_handoff dashboard_version must match")
    manifest_path = handoff.get("manifest_path")
    expected_prefix = f"{dashboard_state.get('evidence_report_directory')}/"
    expected_suffix = f"/{dashboard_state.get('manifest_filename')}"
    if not (
        isinstance(manifest_path, str)
        and manifest_path.startswith(expected_prefix)
        and manifest_path.endswith(expected_suffix)
    ):
        errors.append(f"{source} dashboard_handoff manifest_path must point to 9.7 dashboard")
    status = handoff.get("status")
    if status not in GATE_STATUSES:
        errors.append(f"{source} dashboard_handoff status invalid")
    if status in GAP_DOMAIN_STATUSES:
        errors.extend(_item_findings_valid(handoff, findings, "dashboard_handoff"))
    if manifest.get("example_only") is True and handoff.get("graded_protection_handoff_complete"):
        errors.append(f"{source} static example cannot complete dashboard handoff")
    return errors


def _validate_release_rules(
    manifest: dict[str, Any], findings: dict[str, dict[str, Any]], source: str
) -> list[str]:
    errors: list[str] = []
    release_approved = manifest.get("release_approved") is True
    for finding in findings.values():
        if (
            finding.get("severity") in STOP_SHIP_SEVERITIES
            and finding.get("status") in UNRESOLVED_FINDING_STATUSES
            and release_approved
        ):
            errors.append(
                f"{source} release_approved cannot be true with unresolved P0/P1/P2 findings"
            )
    track_mode = manifest.get("track_mode")
    certificate_obtained = manifest.get("real_mlps_level_2_certificate_obtained") is True
    certificate_artifact_id = manifest.get("certificate_artifact_id")
    if track_mode == "standard_m5" and release_approved:
        if not certificate_obtained or not _stable_slug(certificate_artifact_id):
            errors.append(f"{source} standard_m5 release requires MLPS Level 2 certificate")
    if track_mode == "simplified_v1_5" and not certificate_obtained:
        has_deferral = any(
            finding.get("status") == "deferred"
            and finding.get("severity") in STOP_SHIP_SEVERITIES
            and _finding_has_ticket(finding)
            for finding in findings.values()
        )
        if not has_deferral:
            errors.append(f"{source} simplified_v1_5 certificate deferral requires a finding")
    return errors


def validate_manifest(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_no_sensitive_values(manifest, source))
    errors.extend(_validate_root_fields(manifest, source))
    errors.extend(_validate_static_flags(manifest, source, real_evidence))
    findings = _finding_map(manifest)
    errors.extend(_validate_domain_results(manifest, contract, findings, source))
    errors.extend(_validate_artifact_results(manifest, findings, source))
    errors.extend(_validate_hash_manifest(manifest, source))
    errors.extend(_validate_preservation_receipts(manifest, findings, source))
    errors.extend(_validate_legal_reviews(manifest, findings, source, real_evidence))
    errors.extend(_validate_dashboard_handoff(manifest, contract, findings, source))
    errors.extend(_validate_release_rules(manifest, findings, source))
    for finding in findings.values():
        if not _finding_has_ticket(finding):
            errors.append(f"{source} finding {finding.get('finding_id')} must include ticket refs")
    return errors


def validate_evidence_path(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        relative = path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        errors.append(
            "evidence path must be reports/graded-protection-evidence/<run_id>/evidence_manifest.json"
        )
        return errors
    parts = relative.parts
    if len(parts) != 4 or parts[0] != "reports" or parts[1] != "graded-protection-evidence":
        errors.append(
            "evidence path must be reports/graded-protection-evidence/<run_id>/evidence_manifest.json"
        )
        return errors
    run_id = parts[2]
    if parts[3] != MANIFEST_FILENAME or not _stable_slug(run_id):
        errors.append(
            "evidence path must be reports/graded-protection-evidence/<run_id>/evidence_manifest.json"
        )
        return errors
    if path.exists():
        manifest = load_json(path)
        if isinstance(manifest, dict) and manifest.get("run_id") != run_id:
            errors.append("evidence path run_id directory must equal manifest run_id")
    return errors


def validate_ci_workflow(ci_text: str) -> list[str]:
    errors: list[str] = []
    required_snippets = [
        "graded_protection_evidence: ${{ steps.filter.outputs.graded_protection_evidence }}",
        "graded_protection_evidence:",
        "tools/graded_protection_evidence/**",
        "scripts/validate_graded_protection_evidence.py",
        "tests/test_graded_protection_evidence.py",
        "docs/runbooks/graded-protection-evidence.md",
        "reports/graded-protection-evidence/**",
        "tools/governance_dashboard/**",
        "scripts/validate_governance_dashboard.py",
        "tests/test_governance_dashboard.py",
        "docs/runbooks/governance-dashboard.md",
        "reports/governance-dashboard/**",
        "graded-protection-evidence-validation:",
        "uv run python scripts/validate_graded_protection_evidence.py",
        "validate_graded_protection_evidence.py --evidence",
        "uv run pytest tests/test_graded_protection_evidence.py",
    ]
    for snippet in required_snippets:
        if snippet not in ci_text:
            errors.append(f"ci workflow missing {snippet}")
    job_index = ci_text.find("graded-protection-evidence-validation:")
    if job_index == -1:
        return errors
    next_job = ci_text.find("\n  # =====", job_index + 1)
    job_block = ci_text[job_index : next_job if next_job != -1 else len(ci_text)]
    if "continue-on-error" in job_block:
        errors.append("graded-protection-evidence-validation must not use continue-on-error")
    return errors


def validate_static_assets() -> list[str]:
    errors: list[str] = []
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    example = load_json(EXAMPLE_MANIFEST_PATH)
    if not isinstance(contract, dict):
        return ["contract must be object"]
    if not isinstance(schema, dict):
        return ["schema must be object"]
    if not isinstance(example, dict):
        return ["example manifest must be object"]
    errors.extend(validate_contract(contract))
    errors.extend(validate_schema(schema))
    errors.extend(
        validate_manifest(
            example,
            contract,
            source="graded-protection-example",
            real_evidence=False,
        )
    )
    errors.extend(validate_ci_workflow(CI_WORKFLOW_PATH.read_text(encoding="utf-8")))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", action="append", default=[])
    args = parser.parse_args(argv)
    errors = validate_static_assets()
    contract = load_json(CONTRACT_PATH)
    for evidence_path_text in args.evidence:
        evidence_path = Path(evidence_path_text)
        errors.extend(validate_evidence_path(evidence_path))
        if evidence_path.exists():
            evidence = load_json(evidence_path)
            if isinstance(evidence, dict):
                errors.extend(
                    validate_manifest(
                        evidence,
                        contract,
                        source=str(evidence_path),
                        real_evidence=True,
                    )
                )
            else:
                errors.append(f"{evidence_path} must contain a JSON object")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("graded protection evidence OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
