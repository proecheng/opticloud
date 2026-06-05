"""Validate Story 9.7 cross-cutting governance dashboard assets.

The default validation is static. Future redacted operator evidence is
validated only when passed explicitly with --evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = REPO_ROOT / "tools" / "governance_dashboard"
CONTRACT_PATH = DASHBOARD_DIR / "governance_dashboard_contract.json"
SCHEMA_PATH = DASHBOARD_DIR / "governance_dashboard_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = DASHBOARD_DIR / "governance_dashboard_manifest.example.json"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

DASHBOARD_VERSION = "governance_dashboard_v1"
SOURCE_STORY = "9.7"
REPORT_ROOT = "reports/governance-dashboard"
MANIFEST_FILENAME = "dashboard_manifest.json"
UPSTREAM_SOURCE_IDS = (
    "a11y_quarterly_audit",
    "prometheus_metric_audit",
    "nfr_cost_alerts",
    "nfr_security_p0_drills",
    "wcag_2_2_upgrade_path",
    "error_i18n_audit",
)
VIEWER_ROLES = ("PM", "Security", "UX", "SRE", "Compliance")
KPI_GROUPS = ("a11y", "cost", "compliance", "observability", "security", "error_i18n")
REQUIRED_PANEL_IDS = (
    "quarterly-axe-violation-status",
    "wcag-2-2-upgrade-readiness",
    "prometheus-metric-coverage",
    "nfr-cost-redline-state",
    "nfr-security-p0-drill-state",
    "error-i18n-audit-state",
    "compliance-governance-rollup",
)
ROLLUP_STATUSES = ("green", "yellow", "red", "unknown", "not_run")
SOURCE_SNAPSHOT_STATUSES = ("not_run_example", "current", "stale", "missing", "failed")
PANEL_STATUSES = ("not_run_example", "green", "yellow", "red", "unknown")
GRAFANA_REVIEW_STATUSES = ("not_run_example", "passed", "failed", "missing")
ROLE_REVIEW_STATUSES = ("not_run_example", "passed", "failed", "missing")
ALLOWED_DATA_SOURCE_MODES = ("contract_static", "evidence_manifest", "manual_review")
DISALLOWED_DATA_SOURCE_MODES = {"production_live", "grafana_api", "external_network"}
STOP_SHIP_SEVERITIES = {"P0", "P1", "P2"}
MANIFEST_ROOT_REQUIRED = {
    "source_story",
    "dashboard_version",
    "run_id",
    "example_only",
    "generated_by",
    "commit_sha",
    "cadence_mode",
    "period",
    "overall_rollup_status",
    "kpi_rollups",
    "source_snapshots",
    "panel_results",
    "grafana_reviews",
    "role_reviews",
    "findings",
    "redaction_reviewed",
    "release_approved",
    "real_grafana_dashboard_published",
    "real_datasource_connected",
    "real_role_review_completed",
    "real_evidence_aggregation_completed",
}
STATIC_COMPLETION_FLAGS = {
    "all_source_findings_resolved",
    "external_ticket_created",
    "production_release_approved",
    "real_datasource_connected",
    "real_evidence_aggregation_completed",
    "real_external_ticket_created",
    "real_grafana_dashboard_published",
    "real_role_review_completed",
    "release_approved",
}
UPSTREAM_CONTRACTS: dict[str, dict[str, str]] = {
    "a11y_quarterly_audit": {
        "path": "tools/a11y_audit/quarterly_a11y_contract.json",
        "version_key": "audit_version",
    },
    "prometheus_metric_audit": {
        "path": "tools/prometheus_metric_audit/business_metric_audit_contract.json",
        "version_key": "audit_version",
    },
    "nfr_cost_alerts": {
        "path": "tools/nfr_cost_alerts/nfr_cost_alert_contract.json",
        "version_key": "alert_version",
    },
    "nfr_security_p0_drills": {
        "path": "tools/nfr_security_p0_drills/nfr_security_p0_drill_contract.json",
        "version_key": "drill_version",
    },
    "wcag_2_2_upgrade_path": {
        "path": "tools/wcag_2_2_upgrade/wcag_2_2_upgrade_contract.json",
        "version_key": "upgrade_version",
    },
    "error_i18n_audit": {
        "path": "tools/error_i18n_audit/error_i18n_audit_contract.json",
        "version_key": "audit_version",
    },
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
    "grafana_token",
    "grafana_api_key",
    "prometheus_token",
    "prometheus_datasource_credentials",
    "dashboard_share_token",
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
    "raw_metric_labels",
    "metric_labels_raw",
}
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"token|cookie|grafana[_-]?(token|api[_-]?key|secret)|"
    r"prometheus[_-]?(token|datasource|credential|secret)|share[_-]?token|"
    r"tenant[_-]?id|customer[_-]?id|user[_-]?id|account[_-]?id|email|phone|"
    r"prompt|provider[_-]?payload|provider[_-]?request|provider[_-]?response|"
    r"raw[_-]?log|raw[_-]?screenshot|raw[_-]?metric[_-]?labels|"
    r"customer[_-]?identifying)([_-]|$)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_PATTERNS = {
    "email address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone number": re.compile(r"\b(?:\+?86|\+?1)?[-\s(]*\d{3}[-)\s]*\d{3,4}[-\s]*\d{4}\b"),
    "bearer token": re.compile(r"bearer\s+[a-z0-9._~+/=-]{12,}", re.IGNORECASE),
    "api key assignment": re.compile(
        r"(api[_-]?key|token|secret|grafana|prometheus)\s*[:=]\s*[a-z0-9._~+/=-]{12,}",
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


def discover_upstream_state() -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for source_id in UPSTREAM_SOURCE_IDS:
        config = UPSTREAM_CONTRACTS[source_id]
        contract_path = config["path"]
        contract = load_json(REPO_ROOT / contract_path)
        evidence = contract.get("evidence") if isinstance(contract, dict) else None
        boundaries = contract.get("boundaries") if isinstance(contract, dict) else None
        false_boundaries = sorted(
            key
            for key, value in (boundaries or {}).items()
            if isinstance(key, str) and value is False
        )
        state[source_id] = {
            "source_story": contract.get("source_story"),
            "version_key": config["version_key"],
            "version": contract.get(config["version_key"]),
            "contract_path": contract_path,
            "evidence_report_directory": evidence.get("report_directory")
            if isinstance(evidence, dict)
            else None,
            "manifest_filename": evidence.get("manifest_filename")
            if isinstance(evidence, dict)
            else None,
            "boundaries_false": false_boundaries,
        }
    return state


def _upstream_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources = contract.get("upstream_sources")
    if not isinstance(sources, list):
        return {}
    return {
        str(item.get("source_id")): item
        for item in sources
        if isinstance(item, dict) and isinstance(item.get("source_id"), str)
    }


def _panel_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    panels = contract.get("panel_catalog")
    if not isinstance(panels, list):
        return {}
    return {
        str(item.get("panel_id")): item
        for item in panels
        if isinstance(item, dict) and isinstance(item.get("panel_id"), str)
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_values: dict[str, Any] = {
        "dashboard_version": DASHBOARD_VERSION,
        "source_story": SOURCE_STORY,
        "epic": 9,
        "standard_cadence": "quarterly",
        "dashboard_intent": "grafana_ready_governance_overview",
    }
    for key, expected in expected_values.items():
        if contract.get(key) != expected:
            errors.append(f"governance_dashboard_contract.json {key} must be {expected}")

    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("governance_dashboard_contract.json evidence must be an object")
    else:
        if evidence.get("report_directory") != REPORT_ROOT:
            errors.append("governance_dashboard_contract.json evidence.report_directory drifted")
        if evidence.get("manifest_filename") != MANIFEST_FILENAME:
            errors.append("governance_dashboard_contract.json evidence.manifest_filename drifted")

    if tuple(contract.get("viewer_roles", [])) != VIEWER_ROLES:
        errors.append("governance_dashboard_contract.json viewer roles drifted")
    if tuple(contract.get("kpi_groups", [])) != KPI_GROUPS:
        errors.append("governance_dashboard_contract.json KPI groups drifted")

    sources = contract.get("upstream_sources")
    if not isinstance(sources, list):
        errors.append("governance_dashboard_contract.json upstream_sources must be a list")
        sources = []
    source_ids = [item.get("source_id") for item in sources if isinstance(item, dict)]
    if source_ids != list(UPSTREAM_SOURCE_IDS):
        errors.append("governance_dashboard_contract.json upstream_sources ids must match")
    observed = contract.get("observed_upstream_state")
    if not isinstance(observed, dict):
        errors.append("governance_dashboard_contract.json observed_upstream_state must be object")
    elif observed != discover_upstream_state():
        errors.append("governance_dashboard_contract.json observed_upstream_state drifted")
    observed_state = discover_upstream_state()
    for source_id, item in _upstream_map(contract).items():
        if source_id not in UPSTREAM_SOURCE_IDS:
            errors.append(f"governance_dashboard_contract.json invalid source_id {source_id}")
            continue
        for key in (
            "story_id",
            "owner",
            "contract_path",
            "validator_path",
            "runbook_path",
            "evidence_report_directory",
            "manifest_filename",
            "ci_job_name",
            "dashboard_handoff_boundary",
        ):
            if key not in item:
                errors.append(f"governance_dashboard_contract.json {source_id} missing {key}")
        if item.get("story_id") != observed_state[source_id]["source_story"]:
            errors.append(f"governance_dashboard_contract.json {source_id} story_id drifted")
        if item.get("contract_path") != observed_state[source_id]["contract_path"]:
            errors.append(f"governance_dashboard_contract.json {source_id} contract_path drifted")
        if item.get("evidence_report_directory") != observed_state[source_id][
            "evidence_report_directory"
        ]:
            errors.append(
                f"governance_dashboard_contract.json {source_id} evidence_report_directory drifted"
            )
        if item.get("manifest_filename") != observed_state[source_id]["manifest_filename"]:
            errors.append(f"governance_dashboard_contract.json {source_id} manifest_filename drifted")

    panels = contract.get("panel_catalog")
    if not isinstance(panels, list):
        errors.append("governance_dashboard_contract.json panel_catalog must be a list")
        panels = []
    panel_ids = [item.get("panel_id") for item in panels if isinstance(item, dict)]
    if panel_ids != list(REQUIRED_PANEL_IDS):
        errors.append("governance_dashboard_contract.json panel ids must match required panels")
    groups_with_panels = set()
    for panel in panels:
        if not isinstance(panel, dict):
            errors.append("governance_dashboard_contract.json panel must be object")
            continue
        panel_id = panel.get("panel_id")
        for key in (
            "panel_id",
            "title",
            "kpi_group",
            "viewer_roles",
            "upstream_source_id",
            "freshness_sla_days",
            "data_source_mode",
            "query_or_transform",
            "stop_ship_severities",
            "runbook_path",
        ):
            if key not in panel:
                errors.append(f"governance_dashboard_contract.json panel {panel_id} missing {key}")
        kpi_group = panel.get("kpi_group")
        if kpi_group not in KPI_GROUPS:
            errors.append(f"governance_dashboard_contract.json panel {panel_id} invalid KPI group")
        else:
            groups_with_panels.add(str(kpi_group))
        if panel.get("upstream_source_id") not in UPSTREAM_SOURCE_IDS:
            errors.append(
                f"governance_dashboard_contract.json panel {panel_id} references invalid upstream_source_id"
            )
        roles = panel.get("viewer_roles")
        if not isinstance(roles, list) or not roles:
            errors.append(f"governance_dashboard_contract.json panel {panel_id} needs viewer roles")
        elif not set(roles) <= set(VIEWER_ROLES):
            errors.append(f"governance_dashboard_contract.json panel {panel_id} has invalid viewer role")
        if panel.get("data_source_mode") not in ALLOWED_DATA_SOURCE_MODES:
            errors.append(f"governance_dashboard_contract.json panel {panel_id} invalid data source")
        if not isinstance(panel.get("freshness_sla_days"), int):
            errors.append(f"governance_dashboard_contract.json panel {panel_id} freshness_sla_days required")
        if tuple(panel.get("stop_ship_severities", [])) != ("P0", "P1", "P2"):
            errors.append(f"governance_dashboard_contract.json panel {panel_id} stop_ship severities drifted")
    for group in KPI_GROUPS:
        if group not in groups_with_panels:
            errors.append(f"governance_dashboard_contract.json KPI group {group} needs a panel")

    if tuple(contract.get("rollup_statuses", [])) != ROLLUP_STATUSES:
        errors.append("governance_dashboard_contract.json rollup statuses drifted")
    if tuple(contract.get("source_snapshot_statuses", [])) != SOURCE_SNAPSHOT_STATUSES:
        errors.append("governance_dashboard_contract.json source snapshot statuses drifted")
    if tuple(contract.get("panel_statuses", [])) != PANEL_STATUSES:
        errors.append("governance_dashboard_contract.json panel statuses drifted")
    if tuple(contract.get("allowed_data_source_modes", [])) != ALLOWED_DATA_SOURCE_MODES:
        errors.append("governance_dashboard_contract.json data source modes drifted")
    rules = contract.get("stop_ship_rollup_rules")
    if not isinstance(rules, dict):
        errors.append("governance_dashboard_contract.json stop_ship_rollup_rules must be object")
    else:
        for key in (
            "unresolved_p0_p1_p2_forces_red",
            "stale_required_source_forces_at_least_yellow",
            "missing_required_source_forces_red",
        ):
            if rules.get(key) is not True:
                errors.append(f"governance_dashboard_contract.json rollup rule {key} must be true")
    boundaries = contract.get("boundaries")
    if not isinstance(boundaries, dict):
        errors.append("governance_dashboard_contract.json boundaries must be an object")
    else:
        for key in (
            "real_grafana_dashboard_published",
            "real_datasource_connected",
            "real_role_review_completed",
            "real_evidence_aggregation_completed",
            "production_release_approved",
            "real_external_ticket_created",
        ):
            if boundaries.get(key) is not False:
                errors.append(f"governance_dashboard_contract.json boundaries.{key} must be false")
    if set(contract.get("disallowed_static_completion_claims", [])) != STATIC_COMPLETION_FLAGS:
        errors.append("governance_dashboard_contract.json static completion flags drifted")
    errors.extend(validate_no_sensitive_values(contract, "governance_dashboard_contract.json"))
    return errors


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != MANIFEST_ROOT_REQUIRED:
        errors.append("Governance dashboard schema root required fields drifted")
    defs = schema.get("$defs", {})
    if defs.get("sourceId", {}).get("enum") != list(UPSTREAM_SOURCE_IDS):
        errors.append("Governance dashboard schema source enum drifted")
    if defs.get("kpiGroup", {}).get("enum") != list(KPI_GROUPS):
        errors.append("Governance dashboard schema KPI enum drifted")
    if defs.get("viewerRole", {}).get("enum") != list(VIEWER_ROLES):
        errors.append("Governance dashboard schema viewer role enum drifted")
    ticket_required = _schema_required(schema, ["$defs", "ticketRef"])
    if ticket_required != {"ticket_id", "owner", "severity", "due_date", "status"}:
        errors.append("Governance dashboard schema ticketRef required fields drifted")
    errors.extend(validate_no_sensitive_values(schema, "governance_dashboard_manifest.schema.json"))
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
        if not _date(ticket.get("due_date")):
            errors.append(f"{source} finding {finding_id} ticket_ref due_date must be YYYY-MM-DD")
    return errors


def _artifact_path_errors(path_value: Any, run_id: str, source: str, suffixes: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(path_value, str):
        errors.append(f"{source} artifact path must be a string")
        return errors
    normalized = Path(path_value)
    if normalized.is_absolute():
        errors.append(f"{source} artifact path must be repo-relative")
    if ".." in normalized.parts:
        errors.append(f"{source} artifact path must not traverse directories")
    required_prefix = f"{REPORT_ROOT}/{run_id}/"
    if not normalized.as_posix().startswith(required_prefix):
        errors.append(f"{source} artifact path must stay under {required_prefix}")
    if normalized.suffix.lower() not in suffixes:
        errors.append(f"{source} artifact path extension must be one of {sorted(suffixes)}")
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


def _list_by_key(
    manifest: dict[str, Any],
    field: str,
    key: str,
    expected: tuple[str, ...],
    *,
    source: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    rows = manifest.get(field)
    if not isinstance(rows, list):
        errors.append(f"{source} {field} must be a list")
        return {}
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            errors.append(f"{source} {field} row must be object")
            continue
        value = row.get(key)
        if value not in expected:
            errors.append(f"{source} {field} invalid {key} {value}")
            continue
        if value in by_key:
            errors.append(f"{source} {field} duplicate {key} {value}")
        by_key[str(value)] = row
    for value in expected:
        if value not in by_key:
            if key == "kpi_group":
                errors.append(f"{source} {field} missing KPI group {value}")
            elif key == "source_id":
                errors.append(f"{source} {field} missing source {value}")
            elif key == "viewer_role":
                errors.append(f"{source} {field} missing role {value}")
            elif key == "panel_id":
                errors.append(f"{source} {field} missing panel {value}")
            else:
                errors.append(f"{source} {field} missing {key} {value}")
    return by_key


def _validate_kpi_rollups(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    rollups = _list_by_key(
        manifest, "kpi_rollups", "kpi_group", KPI_GROUPS, source=source, errors=errors
    )
    for group, row in rollups.items():
        status = row.get("status")
        if status not in ROLLUP_STATUSES:
            errors.append(f"{source} KPI rollup {group} status invalid")
        if not real_evidence and status != "not_run":
            errors.append(f"{source} example KPI rollup {group} status must be not_run")
        if real_evidence and status == "not_run":
            errors.append(f"{source} real KPI rollup {group} must not be not_run")
        errors.extend(
            _validate_finding_refs(
                row.get("finding_ids"),
                findings,
                source=f"{source} KPI rollup {group}",
                failed=status in {"yellow", "red"},
            )
        )
    return errors


def _validate_source_snapshots(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    snapshots = _list_by_key(
        manifest, "source_snapshots", "source_id", UPSTREAM_SOURCE_IDS, source=source, errors=errors
    )
    run_id = str(manifest.get("run_id", ""))
    for source_id, row in snapshots.items():
        status = row.get("status")
        if status not in SOURCE_SNAPSHOT_STATUSES:
            errors.append(f"{source} source snapshot {source_id} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example source snapshot {source_id} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real source snapshot {source_id} must not be not_run_example")
        errors.extend(
            _artifact_path_errors(
                row.get("artifact_path"),
                run_id,
                f"{source} source snapshot {source_id}",
                {".json"},
            )
        )
        errors.extend(
            _validate_finding_refs(
                row.get("finding_ids"),
                findings,
                source=f"{source} source snapshot {source_id}",
                failed=status in {"stale", "missing", "failed"},
            )
        )
    return errors


def _validate_panel_results(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    panels = _list_by_key(
        manifest, "panel_results", "panel_id", REQUIRED_PANEL_IDS, source=source, errors=errors
    )
    contract_panels = _panel_map(contract)
    run_id = str(manifest.get("run_id", ""))
    for panel_id, row in panels.items():
        expected = contract_panels.get(panel_id, {})
        if row.get("kpi_group") != expected.get("kpi_group"):
            errors.append(f"{source} panel {panel_id} KPI group must match contract")
        if row.get("upstream_source_id") != expected.get("upstream_source_id"):
            errors.append(f"{source} panel {panel_id} upstream source must match contract")
        status = row.get("status")
        if status not in PANEL_STATUSES:
            errors.append(f"{source} panel {panel_id} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example panel {panel_id} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real panel {panel_id} must not be not_run_example")
        mode = row.get("data_source_mode")
        if mode in DISALLOWED_DATA_SOURCE_MODES or mode not in ALLOWED_DATA_SOURCE_MODES:
            errors.append(f"{source} panel {panel_id} invalid data_source_mode")
        errors.extend(
            _artifact_path_errors(
                row.get("artifact_path"),
                run_id,
                f"{source} panel {panel_id}",
                {".json"},
            )
        )
        errors.extend(
            _validate_finding_refs(
                row.get("finding_ids"),
                findings,
                source=f"{source} panel {panel_id}",
                failed=status in {"yellow", "red", "unknown"},
            )
        )
    return errors


def _validate_grafana_reviews(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    reviews = _list_by_key(
        manifest, "grafana_reviews", "panel_id", REQUIRED_PANEL_IDS, source=source, errors=errors
    )
    run_id = str(manifest.get("run_id", ""))
    for panel_id, row in reviews.items():
        status = row.get("status")
        if status not in GRAFANA_REVIEW_STATUSES:
            errors.append(f"{source} Grafana review {panel_id} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example Grafana review {panel_id} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real Grafana review {panel_id} must not be not_run_example")
        if row.get("reviewer_role") not in VIEWER_ROLES:
            errors.append(f"{source} Grafana review {panel_id} reviewer_role invalid")
        errors.extend(
            _artifact_path_errors(
                row.get("artifact_path"),
                run_id,
                f"{source} Grafana review {panel_id}",
                {".png"},
            )
        )
        errors.extend(
            _validate_finding_refs(
                row.get("finding_ids"),
                findings,
                source=f"{source} Grafana review {panel_id}",
                failed=status in {"failed", "missing"},
            )
        )
    return errors


def _validate_role_reviews(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    reviews = _list_by_key(
        manifest, "role_reviews", "viewer_role", VIEWER_ROLES, source=source, errors=errors
    )
    for role, row in reviews.items():
        status = row.get("status")
        if status not in ROLE_REVIEW_STATUSES:
            errors.append(f"{source} role review {role} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example role review {role} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real role review {role} must not be not_run_example")
        errors.extend(
            _validate_finding_refs(
                row.get("finding_ids"),
                findings,
                source=f"{source} role review {role}",
                failed=status in {"failed", "missing"},
            )
        )
    return errors


def validate_manifest(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    missing = MANIFEST_ROOT_REQUIRED - set(manifest)
    for key in sorted(missing):
        errors.append(f"{source} missing required field {key}")
    if manifest.get("source_story") != SOURCE_STORY:
        errors.append(f"{source} source_story must be {SOURCE_STORY}")
    if manifest.get("dashboard_version") != contract.get("dashboard_version"):
        errors.append(f"{source} dashboard_version must match contract")
    if not _stable_slug(manifest.get("run_id")):
        errors.append(f"{source} run_id must be a stable slug")
    if not _commit_sha(manifest.get("commit_sha")):
        errors.append(f"{source} commit_sha must be 7-40 lowercase hex chars")
    if manifest.get("cadence_mode") != "quarterly":
        errors.append(f"{source} cadence_mode must be quarterly")
    if manifest.get("overall_rollup_status") not in ROLLUP_STATUSES:
        errors.append(f"{source} overall_rollup_status invalid")
    if manifest.get("example_only") is not (not real_evidence):
        expected = "false" if real_evidence else "true"
        errors.append(f"{source} example_only must be {expected}")
    if real_evidence:
        if manifest.get("redaction_reviewed") is not True:
            errors.append(f"{source} real evidence redaction_reviewed must be true")
        for flag in (
            "real_role_review_completed",
            "real_evidence_aggregation_completed",
        ):
            if manifest.get(flag) is not True:
                errors.append(f"{source} real evidence {flag} must be true")
    else:
        errors.extend(_validate_static_completion_claims(manifest, source))
        for flag in (
            "real_grafana_dashboard_published",
            "real_datasource_connected",
            "real_role_review_completed",
            "real_evidence_aggregation_completed",
            "release_approved",
        ):
            if manifest.get(flag) is not False:
                errors.append(f"{source} example {flag} must be false")

    period = manifest.get("period")
    if not isinstance(period, dict):
        errors.append(f"{source} period must be an object")
    else:
        if not _date(period.get("start_date")):
            errors.append(f"{source} period.start_date must be YYYY-MM-DD")
        if not _date(period.get("end_date")):
            errors.append(f"{source} period.end_date must be YYYY-MM-DD")

    findings = _finding_map(manifest, source, errors)
    errors.extend(_validate_kpi_rollups(manifest, findings, source=source, real_evidence=real_evidence))
    errors.extend(
        _validate_source_snapshots(manifest, findings, source=source, real_evidence=real_evidence)
    )
    errors.extend(
        _validate_panel_results(
            manifest,
            contract,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
    errors.extend(_validate_grafana_reviews(manifest, findings, source=source, real_evidence=real_evidence))
    errors.extend(_validate_role_reviews(manifest, findings, source=source, real_evidence=real_evidence))
    if manifest.get("release_approved") is True:
        for finding in findings.values():
            if (
                finding.get("severity") in STOP_SHIP_SEVERITIES
                and finding.get("status") != "resolved"
            ):
                errors.append(
                    f"{source} release_approved cannot be true with unresolved "
                    f"{finding.get('severity')} finding {finding.get('finding_id')}"
                )
    for finding in findings.values():
        errors.extend(_validate_ticket_refs(finding, source=source, required=False))
    errors.extend(validate_no_sensitive_values(manifest, source))
    return errors


def validate_evidence_path_mode(path: Path, run_id: str) -> list[str]:
    if path.is_absolute():
        try:
            relative = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        except ValueError:
            return ["Governance dashboard evidence path must be inside the repository"]
    else:
        relative = path.as_posix()
    expected = f"{REPORT_ROOT}/{run_id}/{MANIFEST_FILENAME}"
    if relative != expected:
        return [f"Governance dashboard evidence path must be {expected}"]
    if ".." in Path(relative).parts:
        return ["Governance dashboard evidence path must not traverse directories"]
    return []


def _job_block(workflow: str, job_name: str) -> str:
    marker = f"\n  {job_name}:"
    start = workflow.find(marker)
    if start == -1:
        return ""
    next_job = re.search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + len(marker) :])
    if next_job is None:
        return workflow[start:]
    return workflow[start : start + len(marker) + next_job.start()]


def _filter_block(workflow: str, filter_name: str) -> str:
    marker = f"\n            {filter_name}:\n"
    start = workflow.find(marker)
    if start == -1:
        return ""
    next_filter = re.search(r"\n            [A-Za-z0-9_]+:\n", workflow[start + len(marker) :])
    if next_filter is None:
        return workflow[start:]
    return workflow[start : start + len(marker) + next_filter.start()]


def validate_ci_workflow(workflow_text: str | None = None) -> list[str]:
    workflow = (
        workflow_text if workflow_text is not None else CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    )
    errors: list[str] = []
    for snippet in (
        "governance_dashboard: ${{ steps.filter.outputs.governance_dashboard }}",
        "governance-dashboard-validation:",
    ):
        if snippet not in workflow:
            errors.append(f".github/workflows/ci.yml missing {snippet}")

    filter_block = _filter_block(workflow, "governance_dashboard")
    if not filter_block:
        errors.append(".github/workflows/ci.yml missing governance_dashboard path filter")
    for snippet in (
        "governance_dashboard:",
        "'tools/governance_dashboard/**'",
        "'scripts/validate_governance_dashboard.py'",
        "'tests/test_governance_dashboard.py'",
        "'docs/runbooks/governance-dashboard.md'",
        "'reports/governance-dashboard/**'",
        "'.github/workflows/ci.yml'",
        "'tools/a11y_audit/**'",
        "'scripts/validate_a11y_quarterly_audit.py'",
        "'tests/test_a11y_quarterly_audit.py'",
        "'docs/runbooks/quarterly-a11y-audit.md'",
        "'reports/a11y-quarterly/**'",
        "'tools/prometheus_metric_audit/**'",
        "'scripts/validate_prometheus_metric_audit.py'",
        "'tests/test_prometheus_metric_audit.py'",
        "'docs/runbooks/prometheus-metric-audit.md'",
        "'reports/prometheus-metric-audit/**'",
        "'tools/nfr_cost_alerts/**'",
        "'scripts/validate_nfr_cost_alerts.py'",
        "'tests/test_nfr_cost_alerts.py'",
        "'docs/runbooks/nfr-cost-alerts.md'",
        "'reports/nfr-cost-alerts/**'",
        "'tools/nfr_security_p0_drills/**'",
        "'scripts/validate_nfr_security_p0_drills.py'",
        "'tests/test_nfr_security_p0_drills.py'",
        "'docs/runbooks/nfr-security-p0-drills.md'",
        "'reports/nfr-security-p0-drills/**'",
        "'tools/wcag_2_2_upgrade/**'",
        "'scripts/validate_wcag_2_2_upgrade_path.py'",
        "'tests/test_wcag_2_2_upgrade_path.py'",
        "'docs/runbooks/wcag-2-2-upgrade-path.md'",
        "'reports/wcag-2-2-upgrade/**'",
        "'tools/error_i18n_audit/**'",
        "'scripts/validate_error_i18n_audit.py'",
        "'tests/test_error_i18n_audit.py'",
        "'docs/runbooks/error-i18n-audit.md'",
        "'reports/error-i18n-audit/**'",
    ):
        if snippet not in filter_block:
            errors.append(f".github/workflows/ci.yml governance_dashboard filter missing {snippet}")

    job = _job_block(workflow, "governance-dashboard-validation")
    if not job:
        errors.append(".github/workflows/ci.yml missing governance-dashboard-validation job")
        return errors
    for snippet in (
        "needs.changes.outputs.governance_dashboard == 'true'",
        "uv run python scripts/validate_governance_dashboard.py",
        "uv run python scripts/validate_governance_dashboard.py --evidence",
        "uv run pytest tests/test_governance_dashboard.py -v",
    ):
        if snippet not in job:
            errors.append(f".github/workflows/ci.yml governance dashboard job missing {snippet}")
    if "continue-on-error" in job:
        errors.append("governance-dashboard-validation must not use continue-on-error")
    return errors


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    example_manifest = load_json(EXAMPLE_MANIFEST_PATH)
    if not isinstance(contract, dict):
        return ["governance_dashboard_contract.json must contain an object"]
    errors.extend(validate_contract(contract))
    if not isinstance(schema, dict):
        errors.append("governance_dashboard_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_schema(schema))
    if not isinstance(example_manifest, dict):
        errors.append("governance_dashboard_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_manifest(
                example_manifest,
                contract,
                source="governance_dashboard_manifest.example.json",
                real_evidence=False,
            )
        )
    errors.extend(validate_ci_workflow())
    if evidence_path is not None:
        evidence = load_json(evidence_path)
        if not isinstance(evidence, dict):
            errors.append(f"{evidence_path} must contain an object")
        else:
            run_id = evidence.get("run_id")
            if isinstance(run_id, str):
                errors.extend(validate_evidence_path_mode(evidence_path, run_id))
            else:
                errors.append(f"{evidence_path} run_id must be a string")
            errors.extend(
                validate_manifest(
                    evidence,
                    contract,
                    source=evidence_path.as_posix(),
                    real_evidence=True,
                )
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Optional redacted evidence under reports/governance-dashboard/<run_id>/",
    )
    args = parser.parse_args(argv)
    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("governance dashboard OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
