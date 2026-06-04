"""Validate Story 9.3 NFR-COST red-line alert governance assets.

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
ALERT_DIR = REPO_ROOT / "tools" / "nfr_cost_alerts"
CONTRACT_PATH = ALERT_DIR / "nfr_cost_alert_contract.json"
SCHEMA_PATH = ALERT_DIR / "nfr_cost_alert_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = ALERT_DIR / "nfr_cost_alert_manifest.example.json"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

ALERT_VERSION = "nfr_cost_redline_alerts_v1"
SOURCE_STORY = "9.3"
NFR = "NFR-COST"
REPORT_ROOT = "reports/nfr-cost-alerts"
MANIFEST_FILENAME = "alert_manifest.json"
REDLINE_IDS = (
    "llm_revenue_ratio",
    "gpu_idle_rate",
    "provider_share_revenue_ratio",
    "refund_issued_rate",
    "runway_months",
)
REDLINE_THRESHOLDS: dict[str, dict[str, str | float | int]] = {
    "llm_revenue_ratio": {"comparator": ">=", "value": 0.3, "unit": "ratio"},
    "gpu_idle_rate": {"comparator": ">=", "value": 0.5, "unit": "ratio"},
    "provider_share_revenue_ratio": {"comparator": ">=", "value": 0.5, "unit": "ratio"},
    "refund_issued_rate": {"comparator": ">=", "value": 0.05, "unit": "ratio"},
    "runway_months": {"comparator": "<", "value": 6, "unit": "months"},
}
INPUT_SIGNAL_STATES = ("required", "planned", "missing_with_ticket", "not_applicable")
EVALUATION_STATUSES = ("not_run_example", "passed", "breached", "failed", "not_applicable")
ROUTE_STATUSES = ("not_run_example", "payload_ready", "failed", "not_applicable")
STOP_SHIP_SEVERITIES = {"P0", "P1", "P2"}
MANIFEST_ROOT_REQUIRED = {
    "source_story",
    "alert_version",
    "run_id",
    "example_only",
    "generated_by",
    "commit_sha",
    "cadence_mode",
    "period",
    "redline_evaluations",
    "source_snapshots",
    "prometheus_alerts",
    "dingtalk_payloads",
    "linear_payloads",
    "routing_outcomes",
    "findings",
    "redaction_reviewed",
    "release_approved",
    "real_alert_fired",
    "real_dingtalk_delivered",
    "real_linear_created",
}
STATIC_COMPLETION_FLAGS = {
    "real_alert_fired",
    "real_alertmanager_fired",
    "real_dingtalk_delivered",
    "real_linear_created",
    "real_external_delivery_completed",
    "real_production_breach_observed",
    "finance_approval_completed",
    "release_approved",
    "production_release_approved",
    "external_issue_created",
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
    "webhook_secret",
    "dingtalk_webhook",
    "dingtalk_secret",
    "linear_token",
    "linear_api_key",
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
    "raw_prometheus_labels",
    "raw_metric_labels",
    "raw_finance_export",
    "finance_export_raw",
}
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"token|cookie|webhook|dingtalk[_-]?(webhook|secret|token)|"
    r"linear[_-]?(token|api[_-]?key|secret)|"
    r"tenant[_-]?id|customer[_-]?id|user[_-]?id|account[_-]?id|email|phone|"
    r"prompt|provider[_-]?payload|provider[_-]?request|provider[_-]?response|"
    r"raw[_-]?log|raw[_-]?prometheus[_-]?labels|raw[_-]?metric[_-]?labels|"
    r"raw[_-]?finance[_-]?export)([_-]|$)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_PATTERNS = {
    "email address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone number": re.compile(r"\b(?:\+?86|\+?1)?[-\s(]*\d{3}[-)\s]*\d{3,4}[-\s]*\d{4}\b"),
    "bearer token": re.compile(r"bearer\s+[a-z0-9._~+/=-]{12,}", re.IGNORECASE),
    "api key assignment": re.compile(
        r"(api[_-]?key|token|secret|webhook)\s*[:=]\s*[a-z0-9._~+/=-]{12,}",
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


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _cost_units_from_sql() -> list[str]:
    text = _text("infra/local-init/10-cost-attribution.sql")
    match = re.search(r"cost_unit\s+IN\s+\(([^)]+)\)", text)
    if match is None:
        return []
    return re.findall(r"'([^']+)'", match.group(1))


def _cost_units_from_enum() -> list[str]:
    text = _text("packages/shared-py/opticloud_shared/cost_telemetry/__init__.py")
    values = re.findall(r'=\s+"(llm_token|gpu_second|solver_second)"', text)
    return sorted(set(values), key=("llm_token", "gpu_second", "solver_second").index)


def _hook_state(path: str, helper: str, service: str, cost_unit: str) -> dict[str, Any]:
    text = _text(path)
    helper_start = text.find(f"async def {helper}")
    helper_text = text[helper_start : helper_start + 3000] if helper_start != -1 else ""
    return {
        "path": path,
        "helper": helper,
        "service": service,
        "cost_unit": cost_unit,
        "uses_record_cost_event": "record_cost_event" in helper_text,
    }


def discover_cost_telemetry_state() -> dict[str, Any]:
    sql_text = _text("infra/local-init/10-cost-attribution.sql")
    shared_units = _cost_units_from_enum()
    return {
        "cost_attribution_sql": {
            "path": "infra/local-init/10-cost-attribution.sql",
            "cost_units": _cost_units_from_sql(),
            "has_tenant_service_unit_index": "idx_cost_attr_tenant_service_unit_recorded"
            in sql_text,
            "has_source_id_partial_index": "WHERE source_id IS NOT NULL" in sql_text,
        },
        "shared_cost_unit_enum": {
            "path": "packages/shared-py/opticloud_shared/cost_telemetry/__init__.py",
            "values": shared_units,
        },
        "solver_hook": _hook_state(
            "apps/solver-orchestrator/src/solver_orchestrator/routes.py",
            "_record_solver_cost_attribution",
            "solver-orchestrator",
            "solver_second",
        ),
        "billing_hook": _hook_state(
            "apps/billing-service/src/billing_service/routes.py",
            "_record_billing_cost_attribution",
            "billing-service",
            "solver_second",
        ),
        "prometheus_metric_audit_handoff": {
            "path": "docs/runbooks/prometheus-metric-audit.md",
            "mentions_story_9_3": "Story 9.3" in _text("docs/runbooks/prometheus-metric-audit.md"),
        },
    }


def _redline_catalog_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = contract.get("redline_catalog")
    if not isinstance(catalog, list):
        return {}
    return {
        str(item.get("redline_id")): item
        for item in catalog
        if isinstance(item, dict) and isinstance(item.get("redline_id"), str)
    }


def _threshold_map(contract: dict[str, Any]) -> dict[str, dict[str, str | float | int]]:
    mapped: dict[str, dict[str, str | float | int]] = {}
    for redline_id, item in _redline_catalog_map(contract).items():
        threshold = item.get("threshold")
        if isinstance(threshold, dict):
            mapped[redline_id] = {
                "comparator": threshold.get("comparator"),
                "value": threshold.get("value"),
                "unit": threshold.get("unit"),
            }
    return mapped


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_values: dict[str, Any] = {
        "alert_version": ALERT_VERSION,
        "source_story": SOURCE_STORY,
        "nfr": NFR,
        "standard_cadence": "quarterly",
        "breach_drill_required": True,
    }
    for key, expected in expected_values.items():
        if contract.get(key) != expected:
            errors.append(f"nfr_cost_alert_contract.json {key} must be {expected}")

    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("nfr_cost_alert_contract.json evidence must be an object")
    else:
        if evidence.get("report_directory") != REPORT_ROOT:
            errors.append("nfr_cost_alert_contract.json evidence.report_directory drifted")
        if evidence.get("manifest_filename") != MANIFEST_FILENAME:
            errors.append("nfr_cost_alert_contract.json evidence.manifest_filename drifted")

    if tuple(contract.get("input_signal_states", [])) != INPUT_SIGNAL_STATES:
        errors.append("nfr_cost_alert_contract.json input signal states drifted")
    if tuple(contract.get("evaluation_statuses", [])) != EVALUATION_STATUSES:
        errors.append("nfr_cost_alert_contract.json evaluation statuses drifted")
    if tuple(contract.get("route_statuses", [])) != ROUTE_STATUSES:
        errors.append("nfr_cost_alert_contract.json route statuses drifted")

    catalog = contract.get("redline_catalog")
    if not isinstance(catalog, list):
        errors.append("nfr_cost_alert_contract.json redline_catalog must be a list")
        catalog = []
    redline_ids = [item.get("redline_id") for item in catalog if isinstance(item, dict)]
    if redline_ids != list(REDLINE_IDS):
        errors.append("nfr_cost_alert_contract.json redline_catalog ids must match NFR-COST")
    if _threshold_map(contract) != REDLINE_THRESHOLDS:
        errors.append("nfr_cost_alert_contract.json redline thresholds drifted")

    for redline_id, item in _redline_catalog_map(contract).items():
        for key in ("name", "owner", "severity", "threshold", "prometheus_alert", "input_signals"):
            if key not in item:
                errors.append(f"nfr_cost_alert_contract.json {redline_id} missing {key}")
        alert = item.get("prometheus_alert")
        if not isinstance(alert, dict):
            errors.append(f"nfr_cost_alert_contract.json {redline_id} prometheus_alert must be object")
        else:
            for key in ("alert_name", "promql", "for", "labels", "annotations"):
                if key not in alert:
                    errors.append(f"nfr_cost_alert_contract.json {redline_id} alert missing {key}")
            if "docs/runbooks/nfr-cost-alerts.md" not in json.dumps(alert, ensure_ascii=False):
                errors.append(f"nfr_cost_alert_contract.json {redline_id} alert must reference runbook")
        signals = item.get("input_signals")
        if not isinstance(signals, list) or not signals:
            errors.append(f"nfr_cost_alert_contract.json {redline_id} input_signals required")
        else:
            for signal in signals:
                if not isinstance(signal, dict):
                    errors.append(f"nfr_cost_alert_contract.json {redline_id} signal must be object")
                    continue
                for key in (
                    "signal_id",
                    "source_system",
                    "expected_metric_name",
                    "unit",
                    "aggregation_window",
                    "implementation_state",
                ):
                    if key not in signal:
                        errors.append(f"nfr_cost_alert_contract.json {redline_id} signal missing {key}")
                if signal.get("implementation_state") not in INPUT_SIGNAL_STATES:
                    errors.append(
                        f"nfr_cost_alert_contract.json {redline_id} signal implementation_state invalid"
                    )

    dingtalk = contract.get("dingtalk_ready_payload")
    if not isinstance(dingtalk, dict):
        errors.append("nfr_cost_alert_contract.json dingtalk_ready_payload must be object")
    else:
        for required in (
            "redline_id",
            "severity",
            "markdown_title",
            "markdown_text",
            "summary",
            "runbook_path",
            "evidence_pointer",
        ):
            if required not in dingtalk.get("required_fields", []):
                errors.append(f"nfr_cost_alert_contract.json DingTalk payload missing {required}")
        if "token" in json.dumps(dingtalk, ensure_ascii=False).lower():
            errors.append("nfr_cost_alert_contract.json DingTalk payload must not include token wording")

    linear = contract.get("linear_ready_ticket")
    if not isinstance(linear, dict):
        errors.append("nfr_cost_alert_contract.json linear_ready_ticket must be object")
    else:
        for required in (
            "redline_id",
            "title",
            "description",
            "team_key",
            "labels",
            "severity",
            "owner",
            "due_date_policy",
            "evidence_pointer",
        ):
            if required not in linear.get("required_fields", []):
                errors.append(f"nfr_cost_alert_contract.json Linear payload missing {required}")
        if linear.get("team_key") != "NFR-COST":
            errors.append("nfr_cost_alert_contract.json Linear team key must be NFR-COST")

    observed = contract.get("observed_cost_telemetry_state")
    if not isinstance(observed, dict):
        errors.append("nfr_cost_alert_contract.json observed_cost_telemetry_state must be an object")
    elif observed != discover_cost_telemetry_state():
        errors.append("nfr_cost_alert_contract.json observed_cost_telemetry_state drifted")

    boundaries = contract.get("boundaries")
    if not isinstance(boundaries, dict):
        errors.append("nfr_cost_alert_contract.json boundaries must be an object")
    else:
        for key in (
            "live_prometheus_rule_loaded",
            "real_alertmanager_fired",
            "real_dingtalk_delivered",
            "real_linear_created",
            "real_production_breach_observed",
            "finance_approval_completed",
            "release_approved",
            "external_delivery_in_scope",
            "unified_governance_dashboard_in_scope",
        ):
            if boundaries.get(key) is not False:
                errors.append(f"nfr_cost_alert_contract.json boundaries.{key} must be false")
    if set(contract.get("disallowed_static_completion_claims", [])) != STATIC_COMPLETION_FLAGS:
        errors.append("nfr_cost_alert_contract.json static completion flags drifted")
    errors.extend(validate_no_sensitive_values(contract, "nfr_cost_alert_contract.json"))
    return errors


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != MANIFEST_ROOT_REQUIRED:
        errors.append("NFR-COST alert schema root required fields drifted")
    redline_enum = schema.get("$defs", {}).get("redlineId", {}).get("enum")
    if redline_enum != list(REDLINE_IDS):
        errors.append("NFR-COST alert schema redline enum drifted")
    evaluation_enum = schema.get("$defs", {}).get("evaluationStatus", {}).get("enum")
    if evaluation_enum != list(EVALUATION_STATUSES):
        errors.append("NFR-COST alert schema evaluation status enum drifted")
    route_enum = schema.get("$defs", {}).get("routeStatus", {}).get("enum")
    if route_enum != list(ROUTE_STATUSES):
        errors.append("NFR-COST alert schema route status enum drifted")
    ticket_required = _schema_required(schema, ["$defs", "ticketRef"])
    if ticket_required != {"ticket_id", "owner", "severity", "due_date", "status"}:
        errors.append("NFR-COST alert schema ticketRef required fields drifted")
    errors.extend(validate_no_sensitive_values(schema, "nfr_cost_alert_manifest.schema.json"))
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


def _artifact_path_errors(value: Any, run_id: str, source: str, suffixes: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, str):
        return [f"{source} artifact path must be a string"]
    normalized = Path(value)
    if normalized.is_absolute():
        errors.append(f"{source} artifact path must be relative")
    if ".." in normalized.parts:
        errors.append(f"{source} artifact path must not traverse directories")
    required_prefix = f"{REPORT_ROOT}/{run_id}/"
    if not value.startswith(required_prefix):
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
        errors.append(f"{source} failed or breached check must reference at least one finding")
    for finding_id in ids:
        if finding_id not in findings:
            errors.append(f"{source} references unknown finding {finding_id}")
        else:
            errors.extend(_validate_ticket_refs(findings[finding_id], source=source, required=failed))
    return errors


def _list_by_redline(
    manifest: dict[str, Any],
    field: str,
    *,
    source: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    entries = manifest.get(field)
    if not isinstance(entries, list):
        errors.append(f"{source} {field} must be a list")
        return {}
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append(f"{source} {field} item must be an object")
            continue
        redline_id = entry.get("redline_id")
        if redline_id not in REDLINE_IDS:
            errors.append(f"{source} {field} invalid redline_id {redline_id}")
            continue
        if redline_id in by_id:
            errors.append(f"{source} {field} duplicate redline {redline_id}")
        by_id[str(redline_id)] = entry
    for redline_id in REDLINE_IDS:
        if redline_id not in by_id:
            errors.append(f"{source} {field} missing redline {redline_id}")
    return by_id


def _signal_keys(contract: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for redline_id, item in _redline_catalog_map(contract).items():
        for signal in item.get("input_signals", []):
            if isinstance(signal, dict):
                signal_id = signal.get("signal_id")
                if isinstance(signal_id, str):
                    keys.add((redline_id, signal_id))
    return keys


def _validate_redline_evaluations(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    by_id = _list_by_redline(manifest, "redline_evaluations", source=source, errors=errors)
    thresholds = _threshold_map(contract)
    for redline_id, evaluation in by_id.items():
        status = evaluation.get("status")
        if status not in EVALUATION_STATUSES:
            errors.append(f"{source} redline {redline_id} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example redline {redline_id} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real redline {redline_id} must not be not_run_example")
        if evaluation.get("threshold") != thresholds.get(redline_id):
            errors.append(f"{source} redline {redline_id} threshold must match contract")
        if real_evidence and status in {"passed", "breached", "failed"} and not isinstance(
            evaluation.get("observed_value"), int | float
        ):
            errors.append(f"{source} redline {redline_id} observed_value must be numeric")
        errors.extend(
            _validate_finding_refs(
                evaluation.get("finding_ids"),
                findings,
                source=f"{source} redline {redline_id}",
                failed=status in {"breached", "failed"},
            )
        )
    return errors


def _validate_source_snapshots(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    snapshots = manifest.get("source_snapshots")
    if not isinstance(snapshots, list):
        return [f"{source} source_snapshots must be a list"]
    expected = _signal_keys(contract)
    seen: set[tuple[str, str]] = set()
    run_id = str(manifest.get("run_id", ""))
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            errors.append(f"{source} source snapshot must be an object")
            continue
        key = (str(snapshot.get("redline_id")), str(snapshot.get("signal_id")))
        if key not in expected:
            errors.append(f"{source} source snapshot unexpected signal {key}")
        else:
            if key in seen:
                errors.append(f"{source} source_snapshots duplicate signal {key}")
            seen.add(key)
        status = snapshot.get("status")
        if status not in EVALUATION_STATUSES:
            errors.append(f"{source} source snapshot {key} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example source snapshot {key} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real source snapshot {key} must not be not_run_example")
        errors.extend(
            _artifact_path_errors(
                snapshot.get("artifact_path"),
                run_id,
                f"{source} source snapshot {key}",
                {".json"},
            )
        )
        errors.extend(
            _validate_finding_refs(
                snapshot.get("finding_ids"),
                findings,
                source=f"{source} source snapshot {key}",
                failed=status in {"breached", "failed", "not_applicable"},
            )
        )
    for key in sorted(expected - seen):
        errors.append(f"{source} source_snapshots missing signal {key[0]}.{key[1]}")
    return errors


def _validate_prometheus_alerts(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    by_id = _list_by_redline(manifest, "prometheus_alerts", source=source, errors=errors)
    catalog = _redline_catalog_map(contract)
    run_id = str(manifest.get("run_id", ""))
    for redline_id, alert in by_id.items():
        expected_alert = catalog.get(redline_id, {}).get("prometheus_alert", {})
        if alert.get("alert_name") != expected_alert.get("alert_name"):
            errors.append(f"{source} alert {redline_id} alert_name must match contract")
        status = alert.get("status")
        if status not in EVALUATION_STATUSES:
            errors.append(f"{source} alert {redline_id} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example alert {redline_id} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real alert {redline_id} must not be not_run_example")
        errors.extend(
            _artifact_path_errors(
                alert.get("artifact_path"),
                run_id,
                f"{source} alert {redline_id}",
                {".json"},
            )
        )
        errors.extend(
            _validate_finding_refs(
                alert.get("finding_ids"),
                findings,
                source=f"{source} alert {redline_id}",
                failed=status in {"breached", "failed"},
            )
        )
    return errors


def _validate_dingtalk_payloads(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    by_id = _list_by_redline(manifest, "dingtalk_payloads", source=source, errors=errors)
    run_id = str(manifest.get("run_id", ""))
    expected_pointer = f"{REPORT_ROOT}/{run_id}/{MANIFEST_FILENAME}"
    for redline_id, payload in by_id.items():
        status = payload.get("status")
        if status not in ROUTE_STATUSES:
            errors.append(f"{source} DingTalk payload {redline_id} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example DingTalk payload {redline_id} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real DingTalk payload {redline_id} must not be not_run_example")
        if payload.get("runbook_path") != "docs/runbooks/nfr-cost-alerts.md":
            errors.append(f"{source} DingTalk payload {redline_id} runbook_path drifted")
        if payload.get("evidence_pointer") != expected_pointer:
            errors.append(f"{source} DingTalk payload {redline_id} evidence_pointer drifted")
        errors.extend(
            _validate_finding_refs(
                payload.get("finding_ids"),
                findings,
                source=f"{source} DingTalk payload {redline_id}",
                failed=status == "failed",
            )
        )
    return errors


def _validate_linear_payloads(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    by_id = _list_by_redline(manifest, "linear_payloads", source=source, errors=errors)
    run_id = str(manifest.get("run_id", ""))
    expected_pointer = f"{REPORT_ROOT}/{run_id}/{MANIFEST_FILENAME}"
    for redline_id, payload in by_id.items():
        status = payload.get("status")
        if status not in ROUTE_STATUSES:
            errors.append(f"{source} Linear payload {redline_id} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example Linear payload {redline_id} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real Linear payload {redline_id} must not be not_run_example")
        if payload.get("team_key") != "NFR-COST":
            errors.append(f"{source} Linear payload {redline_id} team_key must be NFR-COST")
        labels = payload.get("labels")
        if not isinstance(labels, list) or not {"nfr-cost", "redline", "governance"} <= set(labels):
            errors.append(f"{source} Linear payload {redline_id} labels missing required set")
        if payload.get("evidence_pointer") != expected_pointer:
            errors.append(f"{source} Linear payload {redline_id} evidence_pointer drifted")
        if payload.get("external_issue_id") is not None:
            errors.append(f"{source} Linear payload {redline_id} external_issue_id must stay null")
        errors.extend(
            _validate_finding_refs(
                payload.get("finding_ids"),
                findings,
                source=f"{source} Linear payload {redline_id}",
                failed=status == "failed",
            )
        )
    return errors


def _validate_routing_outcomes(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    by_id = _list_by_redline(manifest, "routing_outcomes", source=source, errors=errors)
    for redline_id, outcome in by_id.items():
        dingtalk_status = outcome.get("dingtalk_status")
        linear_status = outcome.get("linear_status")
        owner_ack_status = outcome.get("owner_ack_status")
        if dingtalk_status not in ROUTE_STATUSES:
            errors.append(f"{source} routing {redline_id} dingtalk_status invalid")
        if linear_status not in ROUTE_STATUSES:
            errors.append(f"{source} routing {redline_id} linear_status invalid")
        if owner_ack_status not in {"not_run_example", "pending", "acked", "failed"}:
            errors.append(f"{source} routing {redline_id} owner_ack_status invalid")
        if not real_evidence and (
            dingtalk_status != "not_run_example"
            or linear_status != "not_run_example"
            or owner_ack_status != "not_run_example"
        ):
            errors.append(f"{source} example routing {redline_id} statuses must be not_run_example")
        if real_evidence and "not_run_example" in {
            dingtalk_status,
            linear_status,
            owner_ack_status,
        }:
            errors.append(f"{source} real routing {redline_id} must not be not_run_example")
        errors.extend(
            _validate_finding_refs(
                outcome.get("finding_ids"),
                findings,
                source=f"{source} routing {redline_id}",
                failed=dingtalk_status == "failed"
                or linear_status == "failed"
                or owner_ack_status == "failed",
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
    if manifest.get("alert_version") != contract.get("alert_version"):
        errors.append(f"{source} alert_version must match contract")
    if not _stable_slug(manifest.get("run_id")):
        errors.append(f"{source} run_id must be a stable slug")
    if not _commit_sha(manifest.get("commit_sha")):
        errors.append(f"{source} commit_sha must be 7-40 lowercase hex chars")
    if manifest.get("cadence_mode") not in {"quarterly", "breach_drill"}:
        errors.append(f"{source} cadence_mode must be quarterly or breach_drill")
    if manifest.get("example_only") is not (not real_evidence):
        expected = "false" if real_evidence else "true"
        errors.append(f"{source} example_only must be {expected}")
    if real_evidence:
        if manifest.get("redaction_reviewed") is not True:
            errors.append(f"{source} real evidence redaction_reviewed must be true")
        if manifest.get("real_alert_fired") is not True:
            errors.append(f"{source} real evidence real_alert_fired must be true")
    else:
        errors.extend(_validate_static_completion_claims(manifest, source))
        if manifest.get("real_alert_fired") is not False:
            errors.append(f"{source} example real_alert_fired must be false")
        if manifest.get("real_dingtalk_delivered") is not False:
            errors.append(f"{source} example real_dingtalk_delivered must be false")
        if manifest.get("real_linear_created") is not False:
            errors.append(f"{source} example real_linear_created must be false")
        if manifest.get("release_approved") is not False:
            errors.append(f"{source} example release_approved must be false")

    period = manifest.get("period")
    if not isinstance(period, dict):
        errors.append(f"{source} period must be an object")
    else:
        if not _date(period.get("start_date")):
            errors.append(f"{source} period.start_date must be YYYY-MM-DD")
        if not _date(period.get("end_date")):
            errors.append(f"{source} period.end_date must be YYYY-MM-DD")

    findings = _finding_map(manifest, source, errors)
    errors.extend(
        _validate_redline_evaluations(
            manifest,
            contract,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
    errors.extend(
        _validate_source_snapshots(
            manifest,
            contract,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
    errors.extend(
        _validate_prometheus_alerts(
            manifest,
            contract,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
    errors.extend(
        _validate_dingtalk_payloads(
            manifest,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
    errors.extend(
        _validate_linear_payloads(
            manifest,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
    errors.extend(
        _validate_routing_outcomes(
            manifest,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
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
            return ["NFR-COST alert evidence path must be inside the repository"]
    else:
        relative = path.as_posix()
    expected = f"{REPORT_ROOT}/{run_id}/{MANIFEST_FILENAME}"
    if relative != expected:
        return [f"NFR-COST alert evidence path must be {expected}"]
    if ".." in Path(relative).parts:
        return ["NFR-COST alert evidence path must not traverse directories"]
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
        "nfr_cost_alerts: ${{ steps.filter.outputs.nfr_cost_alerts }}",
        "nfr-cost-alerts-validation:",
    ):
        if snippet not in workflow:
            errors.append(f".github/workflows/ci.yml missing {snippet}")

    filter_block = _filter_block(workflow, "nfr_cost_alerts")
    if not filter_block:
        errors.append(".github/workflows/ci.yml missing nfr_cost_alerts path filter")
    for snippet in (
        "nfr_cost_alerts:",
        "'tools/nfr_cost_alerts/**'",
        "'scripts/validate_nfr_cost_alerts.py'",
        "'tests/test_nfr_cost_alerts.py'",
        "'docs/runbooks/nfr-cost-alerts.md'",
        "'reports/nfr-cost-alerts/**'",
        "'.github/workflows/ci.yml'",
        "'infra/local-init/10-cost-attribution.sql'",
        "'packages/shared-py/opticloud_shared/cost_telemetry/**'",
        "'apps/solver-orchestrator/src/solver_orchestrator/routes.py'",
        "'apps/solver-orchestrator/src/solver_orchestrator/models.py'",
        "'apps/billing-service/src/billing_service/routes.py'",
        "'apps/billing-service/src/billing_service/models.py'",
        "'tools/prometheus_metric_audit/**'",
        "'scripts/validate_prometheus_metric_audit.py'",
        "'tests/test_prometheus_metric_audit.py'",
        "'docs/runbooks/prometheus-metric-audit.md'",
        "'reports/prometheus-metric-audit/**'",
    ):
        if snippet not in filter_block:
            errors.append(f".github/workflows/ci.yml nfr_cost_alerts filter missing {snippet}")

    job = _job_block(workflow, "nfr-cost-alerts-validation")
    if not job:
        errors.append(".github/workflows/ci.yml missing nfr-cost-alerts-validation job")
        return errors
    for snippet in (
        "needs.changes.outputs.nfr_cost_alerts == 'true'",
        "uv run python scripts/validate_nfr_cost_alerts.py",
        "uv run python scripts/validate_nfr_cost_alerts.py --evidence",
        "uv run pytest tests/test_nfr_cost_alerts.py -v",
    ):
        if snippet not in job:
            errors.append(f".github/workflows/ci.yml NFR-COST alert job missing {snippet}")
    if "continue-on-error" in job:
        errors.append("nfr-cost-alerts-validation must not use continue-on-error")
    return errors


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    example_manifest = load_json(EXAMPLE_MANIFEST_PATH)
    if not isinstance(contract, dict):
        return ["nfr_cost_alert_contract.json must contain an object"]
    errors.extend(validate_contract(contract))
    if not isinstance(schema, dict):
        errors.append("nfr_cost_alert_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_schema(schema))
    if not isinstance(example_manifest, dict):
        errors.append("nfr_cost_alert_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_manifest(
                example_manifest,
                contract,
                source="nfr_cost_alert_manifest.example.json",
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
        help="Optional redacted evidence under reports/nfr-cost-alerts/<run_id>/",
    )
    args = parser.parse_args(argv)
    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("nfr cost alerts OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
