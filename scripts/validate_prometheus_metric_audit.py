"""Validate Story 9.2 Prometheus business metric audit governance assets.

The default validation is static. Future redacted operator evidence is
validated only when passed explicitly with --evidence.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO_ROOT / "tools" / "prometheus_metric_audit"
CONTRACT_PATH = AUDIT_DIR / "business_metric_audit_contract.json"
SCHEMA_PATH = AUDIT_DIR / "business_metric_audit_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = AUDIT_DIR / "business_metric_audit_manifest.example.json"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

AUDIT_VERSION = "prometheus_business_metric_audit_v1"
SOURCE_STORY = "9.2"
NFR = "NFR-O"
REPORT_ROOT = "reports/prometheus-metric-audit"
MANIFEST_FILENAME = "audit_manifest.json"
METRIC_IDS = (
    "request_count",
    "success_rate",
    "latency",
    "credit_burn",
    "refund_rate",
    "chat",
    "provider_route",
    "reproducibility",
    "sandbox",
    "uptime",
)
API_DIMENSIONS = ("sku", "provider", "service", "endpoint_class", "tenant_tier")
LATENCY_PERCENTILES = ("p50", "p95", "p99")
COVERAGE_STATES = ("covered", "missing_with_ticket", "planned", "not_applicable")
CHECK_STATUSES = ("not_run_example", "passed", "failed", "not_applicable")
STOP_SHIP_SEVERITIES = {"P0", "P1", "P2"}
MANIFEST_ROOT_REQUIRED = {
    "source_story",
    "audit_version",
    "run_id",
    "example_only",
    "generated_by",
    "commit_sha",
    "cadence_mode",
    "period",
    "metric_coverage",
    "scrape_targets",
    "promql_snapshots",
    "grafana_reviews",
    "findings",
    "redaction_reviewed",
    "release_approved",
    "real_grafana_review_completed",
    "real_prometheus_scrape_completed",
}
STATIC_COMPLETION_FLAGS = {
    "real_audit_passed",
    "real_quarterly_review_completed",
    "real_grafana_review_completed",
    "real_prometheus_scrape_completed",
    "real_dashboard_published",
    "release_approved",
    "production_release_approved",
    "external_ticket_created",
    "uptime_sla_approved",
    "status_page_coverage_claimed",
}
FORBIDDEN_LABEL_DIMENSIONS = {
    "tenant_id",
    "user_id",
    "customer_id",
    "email",
    "phone",
    "account_id",
    "api_key",
    "jwt",
    "token",
    "prompt",
    "provider_payload",
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
    "grafana_share_token",
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
    "metric_labels_raw",
}
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"token|cookie|tenant[_-]?id|customer[_-]?id|user[_-]?id|account[_-]?id|"
    r"email|phone|prompt|provider[_-]?payload|provider[_-]?request|provider[_-]?response|"
    r"raw[_-]?log|metric[_-]?labels[_-]?raw|share[_-]?token)([_-]|$)",
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
}

OBSERVABILITY_SOURCE_GLOBS = ("apps/*/src/**/*.py",)


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


def _service_from_path(path: Path) -> str:
    parts = path.as_posix().split("/")
    if len(parts) >= 2 and parts[0] == "apps":
        return parts[1]
    return path.stem


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _first_string_arg(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _has_generate_latest(path: Path) -> bool:
    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    return "generate_latest()" in text and "prometheus_client" in text


def observability_source_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in OBSERVABILITY_SOURCE_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file():
                files.add(path.relative_to(REPO_ROOT))
    return sorted(files, key=lambda item: item.as_posix())


def discover_metrics_endpoints() -> list[dict[str, str]]:
    endpoints: list[dict[str, str]] = []
    for path in observability_source_files():
        absolute = REPO_ROOT / path
        if not absolute.exists() or not _has_generate_latest(path):
            continue
        tree = ast.parse(absolute.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                endpoint = _first_string_arg(decorator)
                if endpoint != "/metrics":
                    continue
                endpoints.append(
                    {
                        "service": _service_from_path(path),
                        "path": path.as_posix(),
                        "endpoint": "/metrics",
                        "exposition": "prometheus_client.generate_latest",
                    }
                )
    return sorted(endpoints, key=lambda item: (item["service"], item["path"], item["endpoint"]))


def discover_metric_declarations() -> list[dict[str, str]]:
    declarations: list[dict[str, str]] = []
    for path in observability_source_files():
        absolute = REPO_ROOT / path
        if not absolute.exists():
            continue
        text = absolute.read_text(encoding="utf-8")
        if "prometheus_client" not in text:
            continue
        tree = ast.parse(text)
        for node in ast.walk(tree):
            call: ast.Call | None = None
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                call = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Call):
                call = node.value
            if call is None:
                continue
            metric_type = _call_name(call.func)
            if metric_type not in {"Counter", "Gauge", "Histogram"}:
                continue
            metric_name = _first_string_arg(call)
            if metric_name is None:
                continue
            declarations.append(
                {
                    "service": _service_from_path(path),
                    "path": path.as_posix(),
                    "metric_name": metric_name,
                    "metric_type": metric_type,
                }
            )
    return sorted(
        declarations,
        key=lambda item: (item["service"], item["path"], item["metric_name"], item["metric_type"]),
    )


def discover_repo_state() -> dict[str, list[dict[str, str]]]:
    return {
        "metrics_endpoints": discover_metrics_endpoints(),
        "metric_declarations": discover_metric_declarations(),
    }


def _metric_catalog_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = contract.get("metric_catalog")
    if not isinstance(catalog, list):
        return {}
    return {
        str(item.get("metric_id")): item
        for item in catalog
        if isinstance(item, dict) and isinstance(item.get("metric_id"), str)
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_values: dict[str, Any] = {
        "audit_version": AUDIT_VERSION,
        "source_story": SOURCE_STORY,
        "nfr": NFR,
        "nfr_o1_scope": True,
        "standard_cadence": "quarterly",
        "lite_cadence": "annual",
    }
    for key, expected in expected_values.items():
        if contract.get(key) != expected:
            errors.append(f"business_metric_audit_contract.json {key} must be {expected}")

    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("business_metric_audit_contract.json evidence must be an object")
    else:
        if evidence.get("report_directory") != REPORT_ROOT:
            errors.append("business_metric_audit_contract.json evidence.report_directory drifted")
        if evidence.get("manifest_filename") != MANIFEST_FILENAME:
            errors.append("business_metric_audit_contract.json evidence.manifest_filename drifted")

    if tuple(contract.get("coverage_states", [])) != COVERAGE_STATES:
        errors.append("business_metric_audit_contract.json coverage states drifted")
    if tuple(contract.get("required_api_dimensions", [])) != API_DIMENSIONS:
        errors.append("business_metric_audit_contract.json API dimensions drifted")
    if set(contract.get("forbidden_metric_label_dimensions", [])) != FORBIDDEN_LABEL_DIMENSIONS:
        errors.append("business_metric_audit_contract.json forbidden label dimensions drifted")
    if tuple(contract.get("latency_percentiles", [])) != LATENCY_PERCENTILES:
        errors.append("business_metric_audit_contract.json latency percentiles drifted")

    catalog = contract.get("metric_catalog")
    if not isinstance(catalog, list):
        errors.append("business_metric_audit_contract.json metric_catalog must be a list")
        catalog = []
    metric_ids = [item.get("metric_id") for item in catalog if isinstance(item, dict)]
    if metric_ids != list(METRIC_IDS):
        errors.append("business_metric_audit_contract.json metric_catalog ids must match NFR-O1")
    catalog_by_id = _metric_catalog_map(contract)
    for metric_id in METRIC_IDS:
        item = catalog_by_id.get(metric_id)
        if item is None:
            continue
        for key in ("domain_group", "owner", "required_dimensions", "expected_prometheus_names", "grafana_panel_id"):
            if key not in item:
                errors.append(f"business_metric_audit_contract.json {metric_id} missing {key}")
        if item.get("coverage_required") is not True:
            errors.append(f"business_metric_audit_contract.json {metric_id} coverage_required must be true")
        if not isinstance(item.get("expected_prometheus_names"), list) or not item.get(
            "expected_prometheus_names"
        ):
            errors.append(f"business_metric_audit_contract.json {metric_id} needs prometheus names")
    for metric_id in ("request_count", "success_rate", "latency"):
        dimensions = catalog_by_id.get(metric_id, {}).get("required_dimensions")
        if tuple(dimensions or []) != API_DIMENSIONS:
            errors.append(f"business_metric_audit_contract.json {metric_id} API dimensions drifted")
    latency = catalog_by_id.get("latency", {})
    if tuple(latency.get("required_percentiles", [])) != LATENCY_PERCENTILES:
        errors.append("business_metric_audit_contract.json latency percentiles must be p50/p95/p99")

    review = contract.get("grafana_dashboard_review")
    if not isinstance(review, dict):
        errors.append("business_metric_audit_contract.json grafana_dashboard_review must be an object")
    else:
        for key in (
            "dashboard_id_required",
            "panel_id_required",
            "time_range_required",
            "screenshot_artifact_required",
            "reviewer_role_required",
        ):
            if review.get(key) is not True:
                errors.append(f"business_metric_audit_contract.json {key} must be true")
        if review.get("data_source") != "prometheus":
            errors.append("business_metric_audit_contract.json Grafana data_source must be prometheus")
        if tuple(review.get("review_outcome_values", [])) != CHECK_STATUSES:
            errors.append("business_metric_audit_contract.json Grafana review statuses drifted")

    observed = contract.get("observed_repo_state")
    if not isinstance(observed, dict):
        errors.append("business_metric_audit_contract.json observed_repo_state must be an object")
    else:
        current = discover_repo_state()
        for key in ("metrics_endpoints", "metric_declarations"):
            if observed.get(key) != current[key]:
                errors.append(f"business_metric_audit_contract.json observed_repo_state.{key} drifted")

    boundaries = contract.get("boundaries")
    if not isinstance(boundaries, dict):
        errors.append("business_metric_audit_contract.json boundaries must be an object")
    else:
        for key in (
            "live_production_scrape_proven",
            "real_grafana_dashboard_published",
            "real_quarterly_review_completed",
            "real_external_ticket_created",
            "uptime_sla_approved",
            "status_page_coverage_claimed",
            "alert_automation_in_scope",
            "unified_governance_dashboard_in_scope",
        ):
            if boundaries.get(key) is not False:
                errors.append(f"business_metric_audit_contract.json boundaries.{key} must be false")
    if set(contract.get("disallowed_static_completion_claims", [])) != STATIC_COMPLETION_FLAGS:
        errors.append("business_metric_audit_contract.json static completion flags drifted")
    errors.extend(validate_no_sensitive_values(contract, "business_metric_audit_contract.json"))
    return errors


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != MANIFEST_ROOT_REQUIRED:
        errors.append("Prometheus metric audit schema root required fields drifted")
    metric_enum = schema.get("$defs", {}).get("metricId", {}).get("enum")
    if metric_enum != list(METRIC_IDS):
        errors.append("Prometheus metric audit schema metric enum drifted")
    coverage_enum = schema.get("$defs", {}).get("coverageState", {}).get("enum")
    if coverage_enum != list(COVERAGE_STATES):
        errors.append("Prometheus metric audit schema coverage state enum drifted")
    check_enum = schema.get("$defs", {}).get("checkStatus", {}).get("enum")
    if check_enum != list(CHECK_STATUSES):
        errors.append("Prometheus metric audit schema check status enum drifted")
    ticket_required = _schema_required(schema, ["$defs", "ticketRef"])
    if ticket_required != {"ticket_id", "owner", "severity", "due_date", "status"}:
        errors.append("Prometheus metric audit schema ticketRef required fields drifted")
    errors.extend(validate_no_sensitive_values(schema, "business_metric_audit_manifest.schema.json"))
    return errors


def _validate_static_completion_claims(manifest: dict[str, Any], source: str) -> list[str]:
    errors: list[str] = []
    for path, value in _walk_values(manifest):
        key = path.rsplit(".", maxsplit=1)[-1]
        if key in STATIC_COMPLETION_FLAGS and value is True:
            errors.append(f"{source} static example cannot claim {key}")
    return errors


def _finding_map(
    manifest: dict[str, Any], source: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
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


def _validate_ticket_refs(
    finding: dict[str, Any],
    *,
    source: str,
    required: bool,
) -> list[str]:
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


def _artifact_path_errors(path_value: Any, run_id: str, source: str, suffixes: set[str]) -> list[str]:
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


def _validate_metric_coverage(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    coverage = manifest.get("metric_coverage")
    if not isinstance(coverage, list):
        return [f"{source} metric_coverage must be a list"]
    seen: set[str] = set()
    contract_catalog = _metric_catalog_map(contract)
    for item in coverage:
        if not isinstance(item, dict):
            errors.append(f"{source} metric_coverage item must be an object")
            continue
        metric_id = item.get("metric_id")
        if metric_id not in METRIC_IDS:
            errors.append(f"{source} metric_coverage invalid metric_id {metric_id}")
            continue
        if metric_id in seen:
            errors.append(f"{source} metric_coverage duplicate metric_id {metric_id}")
        seen.add(str(metric_id))
        status = item.get("status")
        if status not in COVERAGE_STATES:
            errors.append(f"{source} metric {metric_id} status invalid")
        if not real_evidence and status != "planned":
            errors.append(f"{source} example metric {metric_id} status must be planned")
        if real_evidence and status in {"planned", "not_applicable"}:
            errors.append(
                f"{source} real metric {metric_id} must be covered or missing_with_ticket"
            )
        expected = contract_catalog.get(str(metric_id), {})
        if item.get("owner") != expected.get("owner"):
            errors.append(f"{source} metric {metric_id} owner must match contract")
        if item.get("prometheus_names") != expected.get("expected_prometheus_names"):
            errors.append(f"{source} metric {metric_id} prometheus_names must match contract")
        if item.get("dimensions") != expected.get("required_dimensions"):
            errors.append(f"{source} metric {metric_id} dimensions must match contract")
        forbidden = set(item.get("dimensions", [])) & FORBIDDEN_LABEL_DIMENSIONS
        if forbidden:
            errors.append(f"{source} metric {metric_id} contains forbidden dimensions")
        if metric_id == "latency" and tuple(item.get("percentiles", [])) != LATENCY_PERCENTILES:
            errors.append(f"{source} latency percentiles must be p50/p95/p99")
        failed = status == "missing_with_ticket"
        errors.extend(
            _validate_finding_refs(
                item.get("finding_ids"),
                findings,
                source=f"{source} metric {metric_id}",
                failed=failed,
            )
        )
    missing = set(METRIC_IDS) - seen
    for metric_id in sorted(missing):
        errors.append(f"{source} metric_coverage missing metric {metric_id}")
    return errors


def _validate_scrape_targets(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    targets = manifest.get("scrape_targets")
    if not isinstance(targets, list):
        return [f"{source} scrape_targets must be a list"]
    expected_services = {item["service"] for item in discover_metrics_endpoints()}
    seen: set[str] = set()
    for target in targets:
        if not isinstance(target, dict):
            errors.append(f"{source} scrape target must be an object")
            continue
        service = target.get("service")
        endpoint = target.get("endpoint")
        if service not in expected_services:
            errors.append(f"{source} scrape target service {service} is not in repo metrics endpoints")
        else:
            seen.add(str(service))
        if endpoint != "/metrics":
            errors.append(f"{source} scrape target {service} endpoint must be /metrics")
        status = target.get("status")
        if real_evidence and status not in {"passed", "failed", "not_applicable"}:
            errors.append(f"{source} real scrape target {service} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example scrape target {service} status must be not_run_example")
        if real_evidence and status == "passed" and not isinstance(target.get("sample_count"), int):
            errors.append(f"{source} scrape target {service} sample_count must be an integer")
        errors.extend(
            _validate_finding_refs(
                target.get("finding_ids"),
                findings,
                source=f"{source} scrape target {service}",
                failed=status == "failed",
            )
        )
    for service in sorted(expected_services - seen):
        errors.append(f"{source} scrape_targets missing service {service}")
    return errors


def _validate_promql_snapshots(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    snapshots = manifest.get("promql_snapshots")
    if not isinstance(snapshots, list):
        return [f"{source} promql_snapshots must be a list"]
    seen: set[str] = set()
    run_id = str(manifest.get("run_id", ""))
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            errors.append(f"{source} promql snapshot must be an object")
            continue
        metric_id = snapshot.get("metric_id")
        if metric_id not in METRIC_IDS:
            errors.append(f"{source} promql snapshot invalid metric_id {metric_id}")
            continue
        if metric_id in seen:
            errors.append(f"{source} promql_snapshots duplicate metric {metric_id}")
        seen.add(str(metric_id))
        status = snapshot.get("status")
        if real_evidence and status not in {"passed", "failed", "not_applicable"}:
            errors.append(f"{source} real promql snapshot {metric_id} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example promql snapshot {metric_id} status must be not_run_example")
        errors.extend(
            _artifact_path_errors(
                snapshot.get("artifact_path"),
                run_id,
                f"{source} promql snapshot {metric_id}",
                {".json"},
            )
        )
        errors.extend(
            _validate_finding_refs(
                snapshot.get("finding_ids"),
                findings,
                source=f"{source} promql snapshot {metric_id}",
                failed=status == "failed",
            )
        )
    for metric_id in sorted(set(METRIC_IDS) - seen):
        errors.append(f"{source} promql_snapshots missing metric {metric_id}")
    return errors


def _validate_grafana_reviews(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    reviews = manifest.get("grafana_reviews")
    if not isinstance(reviews, list):
        return [f"{source} grafana_reviews must be a list"]
    panels = {
        metric_id: item.get("grafana_panel_id")
        for metric_id, item in _metric_catalog_map(contract).items()
    }
    seen: set[str] = set()
    run_id = str(manifest.get("run_id", ""))
    for review in reviews:
        if not isinstance(review, dict):
            errors.append(f"{source} grafana review must be an object")
            continue
        metric_id = review.get("metric_id")
        if metric_id not in METRIC_IDS:
            errors.append(f"{source} grafana review invalid metric_id {metric_id}")
            continue
        if metric_id in seen:
            errors.append(f"{source} grafana_reviews duplicate metric {metric_id}")
        seen.add(str(metric_id))
        if review.get("data_source") != "prometheus":
            errors.append(f"{source} grafana review {metric_id} data_source must be prometheus")
        if review.get("panel_id") != panels.get(str(metric_id)):
            errors.append(f"{source} grafana review {metric_id} panel_id must match contract")
        status = review.get("review_outcome")
        if real_evidence and status not in {"passed", "failed", "not_applicable"}:
            errors.append(f"{source} real grafana review {metric_id} outcome invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example grafana review {metric_id} outcome must be not_run_example")
        errors.extend(
            _artifact_path_errors(
                review.get("screenshot_artifact_path"),
                run_id,
                f"{source} grafana review {metric_id}",
                {".png"},
            )
        )
        errors.extend(
            _validate_finding_refs(
                review.get("finding_ids"),
                findings,
                source=f"{source} grafana review {metric_id}",
                failed=status == "failed",
            )
        )
    for metric_id in sorted(set(METRIC_IDS) - seen):
        errors.append(f"{source} grafana_reviews missing metric {metric_id}")
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
    if manifest.get("audit_version") != contract.get("audit_version"):
        errors.append(f"{source} audit_version must match contract")
    if not _stable_slug(manifest.get("run_id")):
        errors.append(f"{source} run_id must be a stable slug")
    if not _commit_sha(manifest.get("commit_sha")):
        errors.append(f"{source} commit_sha must be 7-40 lowercase hex chars")
    if manifest.get("cadence_mode") not in {"quarterly", "annual_lite"}:
        errors.append(f"{source} cadence_mode must be quarterly or annual_lite")
    if manifest.get("example_only") is not (not real_evidence):
        expected = "false" if real_evidence else "true"
        errors.append(f"{source} example_only must be {expected}")
    if real_evidence:
        if manifest.get("redaction_reviewed") is not True:
            errors.append(f"{source} real evidence redaction_reviewed must be true")
        if manifest.get("real_grafana_review_completed") is not True:
            errors.append(f"{source} real evidence real_grafana_review_completed must be true")
        if manifest.get("real_prometheus_scrape_completed") is not True:
            errors.append(f"{source} real evidence real_prometheus_scrape_completed must be true")
    else:
        errors.extend(_validate_static_completion_claims(manifest, source))
        if manifest.get("real_grafana_review_completed") is not False:
            errors.append(f"{source} example real_grafana_review_completed must be false")
        if manifest.get("real_prometheus_scrape_completed") is not False:
            errors.append(f"{source} example real_prometheus_scrape_completed must be false")
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
        _validate_metric_coverage(
            manifest,
            contract,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
    errors.extend(
        _validate_scrape_targets(
            manifest,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
    errors.extend(
        _validate_promql_snapshots(
            manifest,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
    errors.extend(
        _validate_grafana_reviews(
            manifest,
            contract,
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
            return ["Prometheus metric audit evidence path must be inside the repository"]
    else:
        relative = path.as_posix()
    expected = f"{REPORT_ROOT}/{run_id}/{MANIFEST_FILENAME}"
    if relative != expected:
        return [f"Prometheus metric audit evidence path must be {expected}"]
    if ".." in Path(relative).parts:
        return ["Prometheus metric audit evidence path must not traverse directories"]
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
        "prometheus_metric_audit: ${{ steps.filter.outputs.prometheus_metric_audit }}",
        "prometheus-metric-audit-validation:",
    ):
        if snippet not in workflow:
            errors.append(f".github/workflows/ci.yml missing {snippet}")

    filter_block = _filter_block(workflow, "prometheus_metric_audit")
    if not filter_block:
        errors.append(".github/workflows/ci.yml missing prometheus_metric_audit path filter")
    for snippet in (
        "prometheus_metric_audit:",
        "'tools/prometheus_metric_audit/**'",
        "'scripts/validate_prometheus_metric_audit.py'",
        "'tests/test_prometheus_metric_audit.py'",
        "'docs/runbooks/prometheus-metric-audit.md'",
        "'reports/prometheus-metric-audit/**'",
        "'.github/workflows/ci.yml'",
        "'apps/*/src/**/*.py'",
    ):
        if snippet not in filter_block:
            errors.append(
                f".github/workflows/ci.yml prometheus_metric_audit filter missing {snippet}"
            )

    job = _job_block(workflow, "prometheus-metric-audit-validation")
    if not job:
        errors.append(".github/workflows/ci.yml missing prometheus-metric-audit-validation job")
        return errors
    for snippet in (
        "needs.changes.outputs.prometheus_metric_audit == 'true'",
        "uv run python scripts/validate_prometheus_metric_audit.py",
        "uv run python scripts/validate_prometheus_metric_audit.py --evidence",
        "uv run pytest tests/test_prometheus_metric_audit.py -v",
    ):
        if snippet not in job:
            errors.append(f".github/workflows/ci.yml prometheus metric audit job missing {snippet}")
    if "continue-on-error" in job:
        errors.append("prometheus-metric-audit-validation must not use continue-on-error")
    return errors


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    example_manifest = load_json(EXAMPLE_MANIFEST_PATH)
    if not isinstance(contract, dict):
        return ["business_metric_audit_contract.json must contain an object"]
    errors.extend(validate_contract(contract))
    if not isinstance(schema, dict):
        errors.append("business_metric_audit_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_schema(schema))
    if not isinstance(example_manifest, dict):
        errors.append("business_metric_audit_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_manifest(
                example_manifest,
                contract,
                source="business_metric_audit_manifest.example.json",
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
        help="Optional redacted evidence under reports/prometheus-metric-audit/<run_id>/",
    )
    args = parser.parse_args(argv)
    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("prometheus metric audit OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
