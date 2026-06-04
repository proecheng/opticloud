"""Validate Story 9.4 NFR-S P0 drill governance assets.

Default validation is static. Future redacted drill evidence is validated only
when passed explicitly with --evidence.
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
DRILL_DIR = REPO_ROOT / "tools" / "nfr_security_p0_drills"
CONTRACT_PATH = DRILL_DIR / "nfr_security_p0_drill_contract.json"
SCHEMA_PATH = DRILL_DIR / "nfr_security_p0_drill_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = DRILL_DIR / "nfr_security_p0_drill_manifest.example.json"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

SOURCE_STORY = "9.4"
DRILL_VERSION = "nfr_security_p0_drills_v1"
NFR = "NFR-S"
REPORT_ROOT = "reports/nfr-security-p0-drills"
MANIFEST_FILENAME = "drill_manifest.json"
SCENARIO_IDS = (
    "sandbox_privilege_escape",
    "data_exfiltration",
    "billing_ledger_corruption",
)
CADENCE_MODES = ("quarterly", "annual_lite")
DRILL_STATUSES = ("not_run_example", "passed", "failed", "blocked", "not_applicable")
REQUIRED_SOP_GATES = (
    "declare_p0",
    "assign_incident_commander",
    "containment_decision",
    "evidence_redaction",
    "postmortem_owner",
    "ticket_closure_review",
)
TIMELINE_FIELDS = (
    "p0_declared_utc",
    "incident_commander_assigned_utc",
    "containment_started_utc",
    "status_page_decision_utc",
    "postmortem_due_utc",
)
POSTMORTEM_SECTIONS = (
    "what_happened",
    "timeline",
    "impact",
    "detection",
    "mitigation",
    "root_cause",
    "follow_ups",
    "prevention",
)
STOP_SHIP_SEVERITIES = {"P0", "P1", "P2"}
MANIFEST_ROOT_REQUIRED = {
    "source_story",
    "drill_version",
    "run_id",
    "example_only",
    "generated_by",
    "commit_sha",
    "cadence_mode",
    "period",
    "scenario_results",
    "source_snapshots",
    "sop_executions",
    "containment_actions",
    "timeline_records",
    "postmortem_templates",
    "findings",
    "redaction_reviewed",
    "release_approved",
    "real_incident_occurred",
    "real_drill_executed",
    "real_public_postmortem_published",
    "real_external_notification_sent",
    "real_customer_impact",
    "real_refund_or_compensation_executed",
}
STATIC_COMPLETION_FLAGS = {
    "real_incident_occurred",
    "real_drill_executed",
    "real_public_postmortem_published",
    "real_external_notification_sent",
    "real_customer_impact",
    "real_refund_or_compensation_executed",
    "release_approved",
    "production_release_approved",
    "security_signoff_completed",
    "external_ticket_created",
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
    "webhook_token",
    "linear_token",
    "tenant_id",
    "customer_id",
    "user_id",
    "account_id",
    "email",
    "phone",
    "prompt",
    "raw_file",
    "raw_log",
    "raw_logs",
    "raw_sql_dump",
    "raw_ledger_rows",
    "provider_payload",
    "provider_request",
    "provider_response",
}
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"token|cookie|tenant[_-]?id|customer[_-]?id|user[_-]?id|account[_-]?id|"
    r"email|phone|prompt|raw[_-]?file|raw[_-]?log|raw[_-]?sql|raw[_-]?ledger|"
    r"provider[_-]?payload|provider[_-]?request|provider[_-]?response|webhook|linear)([_-]|$)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_PATTERNS = {
    "email address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone number": re.compile(r"\b(?:\+?86|\+?1)?[-\s(]*\d{3}[-)\s]*\d{3,4}[-\s]*\d{4}\b"),
    "bearer token": re.compile(r"bearer\s+[a-z0-9._~+/=-]{12,}", re.IGNORECASE),
    "api key assignment": re.compile(
        r"(api[_-]?key|token|secret)\s*[:=]\s*[a-z0-9._~+/=-]{12,}",
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
    "raw ledger": re.compile(r"\b(raw_ledger_rows|SELECT\s+\*\s+FROM\s+credit_transactions)\b", re.IGNORECASE),
    "raw SQL dump": re.compile(r"\b(pg_dump|COPY\s+credit_transactions|raw_sql_dump)\b", re.IGNORECASE),
    "exploit payload": re.compile(
        r"(:\s*\(\)\s*\{|mount\s+-|docker\s+(run|exec|build|pull)\b|nsenter\b|modprobe\b|insmod\b|rm\s+-rf\b)",
        re.IGNORECASE,
    ),
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _group_digest(value: str) -> str:
    return ":".join(value[index : index + 8] for index in range(0, len(value), 8))


def file_sha256(path: Path) -> str:
    return _group_digest(sha256(path.read_bytes()).hexdigest())


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
    return isinstance(value, str) and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value) is not None


def _commit_sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{7,40}", value) is not None


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def discover_repo_state() -> dict[str, Any]:
    billing_schema = (REPO_ROOT / "infra/local-init/03-billing-schema.sql").read_text(
        encoding="utf-8"
    )
    billing_models = (
        REPO_ROOT / "apps/billing-service/src/billing_service/models.py"
    ).read_text(encoding="utf-8")
    billing_routes = (
        REPO_ROOT / "apps/billing-service/src/billing_service/routes.py"
    ).read_text(encoding="utf-8")
    return {
        "sandbox": {
            "audit_plan_sha256": file_sha256(REPO_ROOT / "infra/sandbox-security/audit_plan.json"),
            "attack_scenarios_sha256": file_sha256(
                REPO_ROOT / "infra/sandbox-security/attack_scenarios.json"
            ),
            "validator_path": "scripts/validate_sandbox_security_audit.py",
            "static_ci_only": True,
        },
        "incident_postmortem": {
            "j3_contract_sha256": file_sha256(
                REPO_ROOT / "tools/incidents/j3_sre_incident_contract.json"
            ),
            "status_page_model_sha256": file_sha256(
                REPO_ROOT / "apps/web/src/lib/status-page.ts"
            ),
            "public_postmortem_route_exists": (
                REPO_ROOT / "apps/web/src/app/status/incidents/[incidentId]/page.tsx"
            ).exists(),
            "j3_validator_path": "scripts/validate_j3_incident_contract.py",
        },
        "billing": {
            "ledger_schema_sha256": file_sha256(REPO_ROOT / "infra/local-init/03-billing-schema.sql"),
            "models_sha256": file_sha256(
                REPO_ROOT / "apps/billing-service/src/billing_service/models.py"
            ),
            "saga_orchestrator_sha256": file_sha256(
                REPO_ROOT / "apps/billing-service/src/billing_service/saga_orchestrator.py"
            ),
            "routes_sha256": file_sha256(
                REPO_ROOT / "apps/billing-service/src/billing_service/routes.py"
            ),
            "credit_transactions_table": "CREATE TABLE IF NOT EXISTS credit_transactions" in billing_schema,
            "saga_instances_table": "CREATE TABLE IF NOT EXISTS saga_instances" in billing_schema,
            "credit_transaction_model": "class CreditTransaction" in billing_models,
            "refund_paths_present": "refund" in billing_routes and "refund_reversal" in billing_routes,
        },
        "ci": {
            "workflow_path": ".github/workflows/ci.yml",
            "related_filters": [
                "j3_incident_contract",
                "sandbox_security_audit",
                "nfr_security_p0_drills",
            ],
        },
    }


def _scenario_catalog_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = contract.get("scenario_catalog")
    if not isinstance(catalog, list):
        return {}
    return {
        str(item.get("scenario_id")): item
        for item in catalog
        if isinstance(item, dict) and isinstance(item.get("scenario_id"), str)
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_values: dict[str, Any] = {
        "drill_version": DRILL_VERSION,
        "source_story": SOURCE_STORY,
        "nfr": NFR,
        "standard_cadence": "quarterly",
        "lite_cadence": "annual",
        "postmortem_sla_hours": 24,
        "p0_zero_tolerance": True,
    }
    for key, expected in expected_values.items():
        if contract.get(key) != expected:
            errors.append(f"nfr_security_p0_drill_contract.json {key} must be {expected}")
    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("nfr_security_p0_drill_contract.json evidence must be an object")
    else:
        if evidence.get("report_directory") != REPORT_ROOT:
            errors.append("nfr_security_p0_drill_contract.json evidence.report_directory drifted")
        if evidence.get("manifest_filename") != MANIFEST_FILENAME:
            errors.append("nfr_security_p0_drill_contract.json evidence.manifest_filename drifted")
    if tuple(contract.get("cadence_modes", [])) != CADENCE_MODES:
        errors.append("nfr_security_p0_drill_contract.json cadence modes drifted")
    if tuple(contract.get("drill_statuses", [])) != DRILL_STATUSES:
        errors.append("nfr_security_p0_drill_contract.json drill statuses drifted")
    if tuple(contract.get("required_sop_gates", [])) != REQUIRED_SOP_GATES:
        errors.append("nfr_security_p0_drill_contract.json SOP gates drifted")
    if tuple(contract.get("timeline_fields", [])) != TIMELINE_FIELDS:
        errors.append("nfr_security_p0_drill_contract.json timeline fields drifted")
    if tuple(contract.get("postmortem_sections", [])) != POSTMORTEM_SECTIONS:
        errors.append("nfr_security_p0_drill_contract.json postmortem sections drifted")

    catalog = contract.get("scenario_catalog")
    if not isinstance(catalog, list):
        errors.append("nfr_security_p0_drill_contract.json scenario_catalog must be a list")
        catalog = []
    scenario_ids = [item.get("scenario_id") for item in catalog if isinstance(item, dict)]
    if scenario_ids != list(SCENARIO_IDS):
        errors.append(
            "nfr_security_p0_drill_contract.json scenario_catalog ids must match canonical NFR-S P0 scenarios"
        )
    for scenario_id, item in _scenario_catalog_map(contract).items():
        for key in (
            "p0_class",
            "trigger_hypothesis",
            "owner",
            "primary_substrate",
            "allowed_drill_modes",
            "required_sop_gates",
            "containment_decision_fields",
            "timeline_fields",
            "postmortem_sections",
            "stop_ship_rule",
            "boundary",
        ):
            if key not in item:
                errors.append(f"nfr_security_p0_drill_contract.json {scenario_id} missing {key}")
        if tuple(item.get("required_sop_gates", [])) != REQUIRED_SOP_GATES:
            errors.append(f"nfr_security_p0_drill_contract.json {scenario_id} SOP gates drifted")
        if tuple(item.get("timeline_fields", [])) != TIMELINE_FIELDS:
            errors.append(f"nfr_security_p0_drill_contract.json {scenario_id} timeline drifted")
        if tuple(item.get("postmortem_sections", [])) != POSTMORTEM_SECTIONS:
            errors.append(f"nfr_security_p0_drill_contract.json {scenario_id} postmortem drifted")

    observed = contract.get("observed_repo_state")
    if not isinstance(observed, dict):
        errors.append("nfr_security_p0_drill_contract.json observed_repo_state must be an object")
    else:
        current = discover_repo_state()
        for key in ("sandbox", "incident_postmortem", "billing", "ci"):
            if observed.get(key) != current[key]:
                errors.append(f"nfr_security_p0_drill_contract.json observed_repo_state.{key} drifted")

    boundaries = contract.get("boundaries")
    if not isinstance(boundaries, dict):
        errors.append("nfr_security_p0_drill_contract.json boundaries must be an object")
    else:
        for key in (
            "real_p0_incident_proven",
            "real_exploit_execution_proven",
            "real_data_breach_proven",
            "real_billing_ledger_corruption_proven",
            "real_customer_impact_proven",
            "real_public_postmortem_published",
            "real_external_ticket_created",
            "real_external_notification_sent",
            "real_refund_or_compensation_executed",
            "release_approval_proven",
        ):
            if boundaries.get(key) is not False:
                errors.append(f"nfr_security_p0_drill_contract.json boundaries.{key} must be false")
    if set(contract.get("disallowed_static_completion_claims", [])) != STATIC_COMPLETION_FLAGS:
        errors.append("nfr_security_p0_drill_contract.json static completion flags drifted")
    errors.extend(validate_no_sensitive_values(contract, "nfr_security_p0_drill_contract.json"))
    return errors


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != MANIFEST_ROOT_REQUIRED:
        errors.append("NFR-S P0 drill schema root required fields drifted")
    if schema.get("$defs", {}).get("scenarioId", {}).get("enum") != list(SCENARIO_IDS):
        errors.append("NFR-S P0 drill schema scenario enum drifted")
    if schema.get("$defs", {}).get("cadenceMode", {}).get("enum") != list(CADENCE_MODES):
        errors.append("NFR-S P0 drill schema cadence enum drifted")
    if schema.get("$defs", {}).get("drillStatus", {}).get("enum") != list(DRILL_STATUSES):
        errors.append("NFR-S P0 drill schema status enum drifted")
    ticket_required = _schema_required(schema, ["$defs", "ticketRef"])
    if ticket_required != {"ticket_id", "owner", "severity", "due_date", "status"}:
        errors.append("NFR-S P0 drill schema ticketRef required fields drifted")
    errors.extend(validate_no_sensitive_values(schema, "nfr_security_p0_drill_manifest.schema.json"))
    return errors


def _validate_static_completion_claims(manifest: dict[str, Any], source: str) -> list[str]:
    errors: list[str] = []
    for path, value in _walk_values(manifest):
        key = path.rsplit(".", maxsplit=1)[-1]
        if key in STATIC_COMPLETION_FLAGS and value is True:
            errors.append(f"{source} static example cannot claim {key}")
    return errors


def _finding_map(manifest: dict[str, Any], source: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    findings = manifest.get("findings")
    if not isinstance(findings, list):
        errors.append(f"{source} findings must be a list")
        return {}
    by_id: dict[str, dict[str, Any]] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            errors.append(f"{source} finding must be an object")
            continue
        finding_id = finding.get("finding_id")
        if not _stable_slug(finding_id):
            errors.append(f"{source} finding_id must be a stable slug")
            continue
        if finding_id in by_id:
            errors.append(f"{source} duplicate finding_id {finding_id}")
        by_id[str(finding_id)] = finding
        for key in ("source", "severity", "status", "summary", "ticket_refs"):
            if key not in finding:
                errors.append(f"{source} finding {finding_id} missing {key}")
    return by_id


def _validate_ticket_refs(finding: dict[str, Any], *, source: str, required: bool) -> list[str]:
    errors: list[str] = []
    finding_id = finding.get("finding_id", "<unknown>")
    ticket_refs = finding.get("ticket_refs")
    if not isinstance(ticket_refs, list):
        return [f"{source} finding {finding_id} ticket_refs must be a list"]
    if required and not ticket_refs:
        errors.append(f"{source} finding {finding_id} must include ticket_refs")
    for ticket in ticket_refs:
        if not isinstance(ticket, dict):
            errors.append(f"{source} finding {finding_id} ticket_ref must be an object")
            continue
        for key in ("ticket_id", "owner", "severity", "due_date", "status"):
            if key not in ticket:
                errors.append(f"{source} finding {finding_id} ticket_ref missing {key}")
        if ticket.get("severity") not in {"P0", "P1", "P2", "P3"}:
            errors.append(f"{source} finding {finding_id} ticket_ref severity invalid")
        if ticket.get("status") not in {"open", "in_progress", "resolved", "deferred"}:
            errors.append(f"{source} finding {finding_id} ticket_ref status invalid")
        if not _date(ticket.get("due_date")):
            errors.append(f"{source} finding {finding_id} ticket_ref due_date invalid")
    return errors


def _validate_finding_refs(
    ids: Any,
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    failed: bool,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(ids, list):
        return [f"{source} finding_ids must be a list"]
    if failed and not ids:
        errors.append(f"{source} failed or missing check must reference at least one finding")
    for finding_id in ids:
        if finding_id not in findings:
            errors.append(f"{source} references unknown finding {finding_id}")
        else:
            errors.extend(_validate_ticket_refs(findings[finding_id], source=source, required=failed))
    return errors


def _artifact_path_errors(path_value: Any, run_id: str, source: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(path_value, str):
        return [f"{source} artifact path must be a string"]
    if "://" in path_value:
        errors.append(f"{source} artifact path must not be a URL")
    if path_value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", path_value):
        errors.append(f"{source} artifact path must be repository-relative")
    normalized = Path(path_value)
    if ".." in normalized.parts:
        errors.append(f"{source} artifact path must not traverse directories")
    required_prefix = f"{REPORT_ROOT}/{run_id}/"
    if not path_value.startswith(required_prefix):
        errors.append(f"{source} artifact path must stay under {required_prefix}")
    if normalized.suffix.lower() != ".json":
        errors.append(f"{source} artifact path must be .json")
    return errors


def _validate_scenario_collection(
    items: Any,
    *,
    source: str,
    name: str,
    findings: dict[str, dict[str, Any]],
    real_evidence: bool,
    require_all: bool,
    run_id: str,
    unique_per_scenario: bool = True,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(items, list):
        return [f"{source} {name} must be a list"]
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            errors.append(f"{source} {name} item must be an object")
            continue
        scenario_id = item.get("scenario_id")
        if scenario_id not in SCENARIO_IDS:
            errors.append(f"{source} {name} invalid scenario_id {scenario_id}")
            continue
        if unique_per_scenario and str(scenario_id) in seen:
            errors.append(f"{source} {name} duplicate scenario {scenario_id}")
        seen.add(str(scenario_id))
        status = item.get("status")
        if status not in DRILL_STATUSES:
            errors.append(f"{source} {name} {scenario_id} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example {name} {scenario_id} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real {name} {scenario_id} must not be not_run_example")
        failed = status in {"failed", "blocked"} or (real_evidence and status == "not_applicable")
        if "artifact_path" in item:
            errors.extend(_artifact_path_errors(item.get("artifact_path"), run_id, f"{source} {name} {scenario_id}"))
        errors.extend(
            _validate_finding_refs(
                item.get("finding_ids"),
                findings,
                source=f"{source} {name} {scenario_id}",
                failed=failed,
            )
        )
    if require_all:
        missing = set(SCENARIO_IDS) - seen
        for scenario_id in sorted(missing):
            errors.append(f"{source} {name} missing scenario {scenario_id}")
    return errors


def _validate_sop_gates(
    items: Any,
    *,
    source: str,
    findings: dict[str, dict[str, Any]],
    real_evidence: bool,
    run_id: str,
) -> list[str]:
    errors = _validate_scenario_collection(
        items,
        source=source,
        name="sop_executions",
        findings=findings,
        real_evidence=real_evidence,
        require_all=True,
        run_id=run_id,
        unique_per_scenario=False,
    )
    if not isinstance(items, list):
        return errors
    seen: dict[str, set[str]] = {scenario_id: set() for scenario_id in SCENARIO_IDS}
    for item in items:
        if isinstance(item, dict) and item.get("scenario_id") in SCENARIO_IDS:
            scenario_id = str(item["scenario_id"])
            gate_id = item.get("gate_id")
            if gate_id not in REQUIRED_SOP_GATES:
                errors.append(f"{source} sop_executions {item.get('scenario_id')} invalid gate_id {gate_id}")
            else:
                if str(gate_id) in seen[scenario_id]:
                    errors.append(f"{source} sop_executions duplicate gate {gate_id} for {scenario_id}")
                seen[scenario_id].add(str(gate_id))
    if real_evidence:
        for scenario_id, gates in seen.items():
            missing = set(REQUIRED_SOP_GATES) - gates
            for gate_id in sorted(missing):
                errors.append(f"{source} sop_executions missing gate {gate_id} for {scenario_id}")
    return errors


def _validate_timeline_records(
    items: Any,
    *,
    source: str,
    findings: dict[str, dict[str, Any]],
    real_evidence: bool,
    run_id: str,
) -> list[str]:
    errors = _validate_scenario_collection(
        items,
        source=source,
        name="timeline_records",
        findings=findings,
        real_evidence=real_evidence,
        require_all=True,
        run_id=run_id,
    )
    if not isinstance(items, list):
        return errors
    for item in items:
        if not isinstance(item, dict) or item.get("scenario_id") not in SCENARIO_IDS:
            continue
        parsed: dict[str, datetime] = {}
        for field in TIMELINE_FIELDS:
            parsed_value = _parse_utc(item.get(field))
            if parsed_value is None:
                errors.append(f"{source} timeline_records {item.get('scenario_id')} {field} invalid")
            else:
                parsed[field] = parsed_value
        if set(parsed) == set(TIMELINE_FIELDS):
            if parsed["incident_commander_assigned_utc"] < parsed["p0_declared_utc"]:
                errors.append(f"{source} incident commander assignment precedes P0 declaration")
            if parsed["containment_started_utc"] < parsed["p0_declared_utc"]:
                errors.append(f"{source} containment precedes P0 declaration")
            expected_due = parsed["p0_declared_utc"] + timedelta(hours=24)
            if parsed["postmortem_due_utc"] != expected_due:
                errors.append(f"{source} postmortem_due_utc must be exactly 24h after p0_declared_utc")
    return errors


def _validate_postmortems(
    items: Any,
    *,
    source: str,
    findings: dict[str, dict[str, Any]],
    real_evidence: bool,
    run_id: str,
) -> list[str]:
    errors = _validate_scenario_collection(
        items,
        source=source,
        name="postmortem_templates",
        findings=findings,
        real_evidence=real_evidence,
        require_all=True,
        run_id=run_id,
    )
    if not isinstance(items, list):
        return errors
    for item in items:
        if not isinstance(item, dict) or item.get("scenario_id") not in SCENARIO_IDS:
            continue
        sections = item.get("sections")
        if not isinstance(sections, dict):
            errors.append(f"{source} postmortem_templates {item.get('scenario_id')} sections must be an object")
            continue
        missing = set(POSTMORTEM_SECTIONS) - set(sections)
        for section in sorted(missing):
            errors.append(f"{source} postmortem_templates {item.get('scenario_id')} missing section {section}")
    return errors


def validate_manifest(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    run_id = manifest.get("run_id")
    if not _stable_slug(run_id):
        return [f"{source} run_id must be a stable slug"]
    missing = MANIFEST_ROOT_REQUIRED - set(manifest)
    for key in sorted(missing):
        errors.append(f"{source} missing required field {key}")
    if manifest.get("source_story") != SOURCE_STORY:
        errors.append(f"{source} source_story must be {SOURCE_STORY}")
    if manifest.get("drill_version") != contract.get("drill_version"):
        errors.append(f"{source} drill_version must match contract")
    if not _commit_sha(manifest.get("commit_sha")):
        errors.append(f"{source} commit_sha must be 7-40 lowercase hex chars")
    if manifest.get("cadence_mode") not in CADENCE_MODES:
        errors.append(f"{source} cadence_mode invalid")
    period = manifest.get("period")
    if not isinstance(period, dict):
        errors.append(f"{source} period must be an object")
    else:
        if not _date(period.get("start_date")):
            errors.append(f"{source} period.start_date must be YYYY-MM-DD")
        if not _date(period.get("end_date")):
            errors.append(f"{source} period.end_date must be YYYY-MM-DD")
    if real_evidence:
        if manifest.get("example_only") is not False:
            errors.append(f"{source} real evidence must set example_only=false")
        if manifest.get("redaction_reviewed") is not True:
            errors.append(f"{source} real evidence redaction_reviewed must be true")
        if manifest.get("real_drill_executed") is not True:
            errors.append(f"{source} real evidence real_drill_executed must be true")
        for key in (
            "real_incident_occurred",
            "real_public_postmortem_published",
            "real_external_notification_sent",
            "real_customer_impact",
            "real_refund_or_compensation_executed",
        ):
            if manifest.get(key) is not False:
                errors.append(f"{source} real evidence cannot claim {key}")
    else:
        if manifest.get("example_only") is not True:
            errors.append(f"{source} static example must set example_only=true")
        errors.extend(_validate_static_completion_claims(manifest, source))
    findings = _finding_map(manifest, source, errors)
    errors.extend(
        _validate_scenario_collection(
            manifest.get("scenario_results"),
            source=source,
            name="scenario_results",
            findings=findings,
            real_evidence=real_evidence,
            require_all=True,
            run_id=str(run_id),
        )
    )
    errors.extend(
        _validate_scenario_collection(
            manifest.get("source_snapshots"),
            source=source,
            name="source_snapshots",
            findings=findings,
            real_evidence=real_evidence,
            require_all=True,
            run_id=str(run_id),
        )
    )
    errors.extend(
        _validate_sop_gates(
            manifest.get("sop_executions"),
            source=source,
            findings=findings,
            real_evidence=real_evidence,
            run_id=str(run_id),
        )
    )
    errors.extend(
        _validate_scenario_collection(
            manifest.get("containment_actions"),
            source=source,
            name="containment_actions",
            findings=findings,
            real_evidence=real_evidence,
            require_all=True,
            run_id=str(run_id),
        )
    )
    errors.extend(
        _validate_timeline_records(
            manifest.get("timeline_records"),
            source=source,
            findings=findings,
            real_evidence=real_evidence,
            run_id=str(run_id),
        )
    )
    errors.extend(
        _validate_postmortems(
            manifest.get("postmortem_templates"),
            source=source,
            findings=findings,
            real_evidence=real_evidence,
            run_id=str(run_id),
        )
    )
    if manifest.get("release_approved") is True:
        for finding in findings.values():
            severity = finding.get("severity")
            status = finding.get("status")
            if severity in STOP_SHIP_SEVERITIES and status in {"open", "in_progress", "deferred"}:
                errors.append(
                    f"{source} release_approved cannot be true with unresolved {severity} finding"
                )
    for finding in findings.values():
        errors.extend(_validate_ticket_refs(finding, source=source, required=False))
    errors.extend(validate_no_sensitive_values(manifest, source))
    return errors


def validate_evidence_path_mode(path: Path, run_id: str) -> list[str]:
    relative = path.as_posix()
    expected = f"{REPORT_ROOT}/"
    if not relative.startswith(expected) or not relative.endswith(f"/{MANIFEST_FILENAME}"):
        return [
            "NFR-S P0 drill evidence path must be "
            f"{REPORT_ROOT}/<run_id>/{MANIFEST_FILENAME}"
        ]
    parts = Path(relative).parts
    if len(parts) < 4 or parts[2] != run_id:
        return ["NFR-S P0 drill evidence path directory must match run_id"]
    return []


def _repo_relative(path: Path, flag: str, errors: list[str]) -> Path:
    try:
        return Path(path.resolve().relative_to(REPO_ROOT.resolve()).as_posix())
    except ValueError:
        errors.append(f"{flag} path must be inside the repository")
        return Path(path.as_posix())


def _filter_block(workflow: str, filter_name: str) -> str:
    marker = f"            {filter_name}:\n"
    start = workflow.find(marker)
    if start == -1:
        return ""
    next_filter = re.search(r"\n            [a-zA-Z0-9_]+:\n", workflow[start + len(marker) :])
    if next_filter is None:
        return workflow[start:]
    return workflow[start : start + len(marker) + next_filter.start()]


def _job_block(workflow: str, job_name: str) -> str:
    marker = f"  {job_name}:\n"
    start = workflow.find(marker)
    if start == -1:
        return ""
    next_job = re.search(r"\n  [a-zA-Z0-9_-]+:\n", workflow[start + len(marker) :])
    if next_job is None:
        return workflow[start:]
    return workflow[start : start + len(marker) + next_job.start()]


def validate_ci_workflow(workflow: str) -> list[str]:
    errors: list[str] = []
    if "nfr_security_p0_drills: ${{ steps.filter.outputs.nfr_security_p0_drills }}" not in workflow:
        errors.append("ci.yml missing nfr_security_p0_drills output")
    block = _filter_block(workflow, "nfr_security_p0_drills")
    if not block:
        errors.append("ci.yml missing nfr_security_p0_drills filter")
    else:
        required_filters = (
            "tools/nfr_security_p0_drills/**",
            "scripts/validate_nfr_security_p0_drills.py",
            "tests/test_nfr_security_p0_drills.py",
            "docs/runbooks/nfr-security-p0-drills.md",
            "reports/nfr-security-p0-drills/**",
            ".github/workflows/ci.yml",
            "infra/sandbox-security/**",
            "tools/incidents/**",
            "scripts/validate_j3_incident_contract.py",
            "apps/web/src/lib/status-page.ts",
            "infra/local-init/03-billing-schema.sql",
            "apps/billing-service/src/billing_service/models.py",
            "apps/billing-service/src/billing_service/saga_orchestrator.py",
            "apps/billing-service/src/billing_service/routes.py",
        )
        for item in required_filters:
            if f"'{item}'" not in block:
                errors.append(f"nfr_security_p0_drills filter missing '{item}'")
    job = _job_block(workflow, "nfr-security-p0-drills-validation")
    if not job:
        errors.append("ci.yml missing nfr-security-p0-drills-validation job")
    else:
        for snippet in (
            "uv run python scripts/validate_nfr_security_p0_drills.py",
            "reports/nfr-security-p0-drills/**/drill_manifest.json",
            "uv run python scripts/validate_nfr_security_p0_drills.py --evidence",
            "uv run pytest tests/test_nfr_security_p0_drills.py -v",
        ):
            if snippet not in job:
                errors.append(f"nfr-security-p0-drills-validation job missing {snippet}")
        if "continue-on-error" in job:
            errors.append("nfr-security-p0-drills-validation job must not use continue-on-error")
    return errors


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    example = load_json(EXAMPLE_MANIFEST_PATH)
    if not isinstance(contract, dict):
        return ["nfr_security_p0_drill_contract.json must contain an object"]
    errors.extend(validate_contract(contract))
    if not isinstance(schema, dict):
        errors.append("nfr_security_p0_drill_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_schema(schema))
    if not isinstance(example, dict):
        errors.append("nfr_security_p0_drill_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_manifest(
                example,
                contract,
                source="nfr_security_p0_drill_manifest.example.json",
                real_evidence=False,
            )
        )
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    errors.extend(validate_ci_workflow(workflow))
    if evidence_path is not None:
        evidence = load_json(evidence_path)
        if not isinstance(evidence, dict):
            errors.append(f"{evidence_path} must contain an object")
        else:
            relative = _repo_relative(evidence_path, "--evidence", errors)
            run_id = evidence.get("run_id")
            if isinstance(run_id, str):
                errors.extend(validate_evidence_path_mode(relative, run_id))
            else:
                errors.append(f"{relative.as_posix()} run_id must be a string")
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
        help="Optional redacted drill manifest under reports/nfr-security-p0-drills/<run_id>/",
    )
    args = parser.parse_args(argv)
    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("nfr security p0 drills OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
