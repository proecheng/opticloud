"""Validate Story 9.5 WCAG 2.2 upgrade-path governance assets.

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
UPGRADE_DIR = REPO_ROOT / "tools" / "wcag_2_2_upgrade"
CONTRACT_PATH = UPGRADE_DIR / "wcag_2_2_upgrade_contract.json"
SCHEMA_PATH = UPGRADE_DIR / "wcag_2_2_upgrade_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = UPGRADE_DIR / "wcag_2_2_upgrade_manifest.example.json"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

UPGRADE_VERSION = "wcag_2_2_upgrade_path_v1"
SOURCE_STORY = "9.5"
NFR = "NFR-A"
REPORT_ROOT = "reports/wcag-2-2-upgrade"
MANIFEST_FILENAME = "upgrade_manifest.json"
PROJECT_CRITERIA_IDS = ("2.4.11", "2.4.12", "2.5.7", "3.2.6")
PROJECT_CRITERIA_LEVELS = ("AA", "AAA", "AA", "A")
DEFERRED_CRITERIA_IDS = ("2.4.13", "2.5.8", "3.3.7", "3.3.8", "3.3.9")
FULL_AA_BLOCKERS = ("2.5.8", "3.3.8")
HOOK_CHECK_IDS = ("focus_not_obscured", "consistent_help_id", "dragging_alternative")
COMPONENT_TARGETS = (
    "useA11y",
    "ConfirmationModal",
    "ExcelDropZone",
    "FilePicker",
    "Console consistent help placement",
)
SOURCE_SNAPSHOT_IDS = (
    "use_a11y",
    "confirmation_modal",
    "excel_drop_zone",
    "file_picker",
    "ui_package",
    "story_9_1",
    "ci_workflow",
)
MANIFEST_ROOT_REQUIRED = {
    "source_story",
    "upgrade_version",
    "run_id",
    "example_only",
    "generated_by",
    "commit_sha",
    "cadence_mode",
    "period",
    "criteria_evaluations",
    "hook_v2_checks",
    "component_refactor_checks",
    "source_snapshots",
    "findings",
    "redaction_reviewed",
    "release_approved",
    "real_wcag_2_2_conformance_claimed",
    "real_third_party_audit_completed",
    "real_component_refactor_completed",
}
STATIC_COMPLETION_FLAGS = {
    "real_wcag_2_2_conformance_claimed",
    "real_third_party_audit_completed",
    "real_component_refactor_completed",
    "release_approved",
    "production_release_approved",
    "external_ticket_created",
    "annual_audit_completed",
}
STOP_SHIP_SEVERITIES = {"P0", "P1", "P2"}
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
    "account_id",
    "participant_id",
    "participant_name",
    "participant_email",
    "email",
    "phone",
    "prompt",
    "provider_payload",
    "provider_request",
    "provider_response",
    "raw_browser_log",
    "browser_log",
    "raw_log",
}
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"token|cookie|tenant[_-]?id|customer[_-]?id|user[_-]?id|account[_-]?id|"
    r"participant[_-]?(id|name|email)|email|phone|prompt|provider[_-]?payload|"
    r"provider[_-]?request|provider[_-]?response|raw[_-]?browser[_-]?log|"
    r"browser[_-]?log|raw[_-]?log)([_-]|$)",
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
    "full WCAG conformance claim": re.compile(
        r"\b(full\s+)?WCAG\s+2\.2\s+AA\s+conformance\s+(achieved|complete|passed|proven)\b",
        re.IGNORECASE,
    ),
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


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
    return (
        isinstance(value, str) and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value) is not None
    )


def _commit_sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{7,40}", value) is not None


def discover_ui_state() -> dict[str, Any]:
    use_a11y = _text("packages/ui/src/hooks/useA11y.ts")
    confirmation = _text("packages/ui/src/components/ConfirmationModal/index.tsx")
    excel = _text("packages/ui/src/components/ExcelDropZone/index.tsx")
    file_picker = _text("packages/ui/src/components/FilePicker/index.tsx")
    package_json = load_json(REPO_ROOT / "packages" / "ui" / "package.json")
    package_text = json.dumps(package_json, sort_keys=True)
    story_9_1 = load_json(REPO_ROOT / "tools" / "a11y_audit" / "quarterly_a11y_contract.json")

    return {
        "use_a11y": {
            "path": "packages/ui/src/hooks/useA11y.ts",
            "has_wcag22_option": "wcag22?: UseA11yWcag22Options" in use_a11y,
            "has_focus_not_obscured_option": "focusNotObscured" in use_a11y,
            "has_consistent_help_id_option": "consistentHelpId" in use_a11y,
            "has_dragging_alternative_option": "draggingAlternative" in use_a11y,
            "has_focus_scroll_behavior": "scrollIntoView" in use_a11y and "focusin" in use_a11y,
        },
        "confirmation_modal": {
            "path": "packages/ui/src/components/ConfirmationModal/index.tsx",
            "uses_focus_not_obscured": 'focusNotObscured: "minimum"' in confirmation,
        },
        "excel_drop_zone": {
            "path": "packages/ui/src/components/ExcelDropZone/index.tsx",
            "uses_file_picker_alternative": "<FilePicker" in excel,
            "declares_dragging_alternative": "draggingAlternative" in excel
            and "FilePicker" in excel,
            "links_visible_instructions": "ariaDescription" in excel and "-desc" in excel,
        },
        "file_picker": {
            "path": "packages/ui/src/components/FilePicker/index.tsx",
            "has_file_input": 'type="file"' in file_picker,
            "requires_aria_label": "ariaLabel: string" in file_picker,
        },
        "ui_package": {
            "path": "packages/ui/package.json",
            "exports_use_a11y": "./hooks/useA11y" in package_text,
            "test_a11y_uses_vitest": "vitest run" in package_json["scripts"]["test:a11y"],
        },
        "story_9_1": {
            "path": "tools/a11y_audit/quarterly_a11y_contract.json",
            "points_to_story_9_5": story_9_1.get("wcag_2_2_upgrade_story") == "9.5",
            "wcag_2_2_in_story_9_1_scope": story_9_1.get("boundaries", {}).get("wcag_2_2_in_scope")
            is True,
        },
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        "upgrade_version": UPGRADE_VERSION,
        "source_story": SOURCE_STORY,
        "nfr": NFR,
        "baseline_standard": "WCAG 2.1 AA v1",
        "target_gate": "WCAG 2.2 v1.5+ project engineering gate",
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            errors.append(f"wcag_2_2_upgrade_contract.json {key} must be {value}")
    w3c = contract.get("w3c_wcag_2_2")
    if not isinstance(w3c, dict):
        errors.append("wcag_2_2_upgrade_contract.json w3c_wcag_2_2 must be an object")
    else:
        if w3c.get("recommendation_date") != "2023-10-05":
            errors.append("wcag_2_2_upgrade_contract.json recommendation_date must be 2023-10-05")
        if w3c.get("total_new_success_criteria") != 9:
            errors.append("wcag_2_2_upgrade_contract.json total_new_success_criteria must be 9")
        refs = w3c.get("official_references")
        if not isinstance(refs, list) or "https://www.w3.org/TR/WCAG22/" not in refs:
            errors.append("wcag_2_2_upgrade_contract.json must include W3C WCAG22 reference")
    criteria = contract.get("project_p78_criteria")
    ids = [item.get("criterion_id") for item in criteria] if isinstance(criteria, list) else []
    levels = [item.get("level") for item in criteria] if isinstance(criteria, list) else []
    if ids != list(PROJECT_CRITERIA_IDS):
        errors.append("wcag_2_2_upgrade_contract.json project P78 criteria drifted")
    if levels != list(PROJECT_CRITERIA_LEVELS):
        errors.append("wcag_2_2_upgrade_contract.json project P78 criterion levels drifted")
    if contract.get("deferred_wcag_2_2_criteria") != list(DEFERRED_CRITERIA_IDS):
        errors.append(
            "wcag_2_2_upgrade_contract.json deferred criteria must preserve full-AA blockers"
        )
    if contract.get("full_wcag_2_2_aa_blockers") != list(FULL_AA_BLOCKERS):
        errors.append("wcag_2_2_upgrade_contract.json full AA blockers drifted")
    upstream = contract.get("upstream_story")
    if not isinstance(upstream, dict) or upstream.get("story") != "9.1":
        errors.append("wcag_2_2_upgrade_contract.json must link Story 9.1 upstream")
    hook_ids = [
        item.get("check_id")
        for item in contract.get("standard_a11y_hook_v2_readiness", [])
        if isinstance(item, dict)
    ]
    if hook_ids != list(HOOK_CHECK_IDS):
        errors.append("wcag_2_2_upgrade_contract.json hook v2 checks drifted")
    if contract.get("component_refactor_targets") != list(COMPONENT_TARGETS):
        errors.append("wcag_2_2_upgrade_contract.json component refactor targets drifted")
    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("wcag_2_2_upgrade_contract.json evidence must be an object")
    else:
        if evidence.get("report_directory") != REPORT_ROOT:
            errors.append("wcag_2_2_upgrade_contract.json evidence.report_directory drifted")
        if evidence.get("manifest_filename") != MANIFEST_FILENAME:
            errors.append("wcag_2_2_upgrade_contract.json evidence.manifest_filename drifted")
    if contract.get("observed_ui_state") != discover_ui_state():
        errors.append("wcag_2_2_upgrade_contract.json observed_ui_state drifted")
    boundaries = contract.get("boundaries")
    if not isinstance(boundaries, dict):
        errors.append("wcag_2_2_upgrade_contract.json boundaries must be an object")
    else:
        for key in (
            "full_wcag_2_2_aa_conformance_proven",
            "third_party_audit_completed",
            "real_disabled_user_panel_completed",
            "all_components_refactored",
            "production_release_approved",
        ):
            if boundaries.get(key) is not False:
                errors.append(f"wcag_2_2_upgrade_contract.json boundaries.{key} must be false")
    if set(contract.get("disallowed_static_completion_claims", [])) != STATIC_COMPLETION_FLAGS:
        errors.append("wcag_2_2_upgrade_contract.json static completion flags drifted")
    boundary = contract.get("boundary_statement")
    if (
        not isinstance(boundary, str)
        or "does not prove full WCAG 2.2 AA conformance" not in boundary
    ):
        errors.append("wcag_2_2_upgrade_contract.json boundary_statement missing full-AA boundary")
    errors.extend(validate_no_sensitive_values(contract, "wcag_2_2_upgrade_contract.json"))
    return errors


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != MANIFEST_ROOT_REQUIRED:
        errors.append("WCAG 2.2 upgrade schema root required fields drifted")
    criterion_enum = schema.get("$defs", {}).get("projectCriterionId", {}).get("enum")
    if criterion_enum != list(PROJECT_CRITERIA_IDS):
        errors.append("WCAG 2.2 upgrade schema criterion enum drifted")
    hook_enum = schema.get("$defs", {}).get("hookCheckId", {}).get("enum")
    if hook_enum != list(HOOK_CHECK_IDS):
        errors.append("WCAG 2.2 upgrade schema hook enum drifted")
    component_enum = schema.get("$defs", {}).get("componentTarget", {}).get("enum")
    if component_enum != list(COMPONENT_TARGETS):
        errors.append("WCAG 2.2 upgrade schema component enum drifted")
    snapshot_enum = schema.get("$defs", {}).get("sourceSnapshotId", {}).get("enum")
    if snapshot_enum != list(SOURCE_SNAPSHOT_IDS):
        errors.append("WCAG 2.2 upgrade schema source snapshot enum drifted")
    ticket_required = _schema_required(schema, ["$defs", "ticketRef"])
    if ticket_required != {"ticket_id", "owner", "severity", "due_date", "status"}:
        errors.append("WCAG 2.2 upgrade schema ticketRef required fields drifted")
    errors.extend(validate_no_sensitive_values(schema, "wcag_2_2_upgrade_manifest.schema.json"))
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
        for key in ("severity", "status", "summary", "ticket_refs"):
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
        errors.append(f"{source} failed finding {finding_id} must include ticket_refs")
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


def _validate_rows(
    rows: Any,
    *,
    source: str,
    row_name: str,
    id_key: str,
    expected_ids: tuple[str, ...],
    findings: dict[str, dict[str, Any]],
    real_evidence: bool,
    failed_message: str,
    allowed_real_statuses: set[str],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(rows, list):
        return [f"{source} {row_name} must be a list"]
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append(f"{source} {row_name} row must be an object")
            continue
        row_id = row.get(id_key)
        if row_id not in expected_ids:
            errors.append(f"{source} {row_name} has invalid {id_key} {row_id}")
            continue
        if row_id in seen:
            errors.append(f"{source} {row_name} duplicate {id_key} {row_id}")
        seen.add(str(row_id))
        status = row.get("status")
        if real_evidence:
            if status not in allowed_real_statuses:
                errors.append(f"{source} real {row_name} status invalid for {row_id}")
        elif status != "not_run_example":
            errors.append(f"{source} example {row_name} status must be not_run_example")
        finding_ids = row.get("finding_ids")
        if not isinstance(finding_ids, list):
            errors.append(f"{source} {row_name} {row_id} finding_ids must be a list")
            finding_ids = []
        for finding_id in finding_ids:
            if finding_id not in findings:
                errors.append(f"{source} {row_name} references unknown finding {finding_id}")
        failed = status in {"failed", "blocked", "stale"}
        if failed and not finding_ids:
            errors.append(f"{source} {failed_message} {row_id} must reference at least one finding")
        for finding_id in finding_ids:
            if finding_id in findings:
                errors.extend(
                    _validate_ticket_refs(
                        findings[finding_id],
                        source=source,
                        required=failed,
                    )
                )
    for missing_id in sorted(set(expected_ids) - seen):
        errors.append(f"{source} {row_name} missing {id_key.replace('_id', '')} {missing_id}")
    return errors


def _validate_criteria_levels(manifest: dict[str, Any], source: str) -> list[str]:
    errors: list[str] = []
    level_by_id = dict(zip(PROJECT_CRITERIA_IDS, PROJECT_CRITERIA_LEVELS, strict=True))
    rows = manifest.get("criteria_evaluations")
    if not isinstance(rows, list):
        return errors
    for row in rows:
        if not isinstance(row, dict):
            continue
        criterion_id = row.get("criterion_id")
        if criterion_id in level_by_id and row.get("level") != level_by_id[criterion_id]:
            errors.append(
                f"{source} criterion {criterion_id} level must be {level_by_id[criterion_id]}"
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
    if manifest.get("upgrade_version") != contract.get("upgrade_version"):
        errors.append(f"{source} upgrade_version must match contract")
    run_id = manifest.get("run_id")
    if not _stable_slug(run_id):
        errors.append(f"{source} run_id must be a stable slug")
    if not _commit_sha(manifest.get("commit_sha")):
        errors.append(f"{source} commit_sha must be 7-40 lowercase hex chars")
    if manifest.get("example_only") is not (not real_evidence):
        expected = "false" if real_evidence else "true"
        errors.append(f"{source} example_only must be {expected}")
    if real_evidence:
        if manifest.get("redaction_reviewed") is not True:
            errors.append(f"{source} real evidence redaction_reviewed must be true")
        if manifest.get("real_wcag_2_2_conformance_claimed") is True:
            errors.append(f"{source} cannot claim full WCAG 2.2 conformance in P78 scope")
    else:
        errors.extend(_validate_static_completion_claims(manifest, source))
    if manifest.get("real_third_party_audit_completed") is not False:
        errors.append(f"{source} real_third_party_audit_completed must be false for Story 9.5")
    period = manifest.get("period")
    if not isinstance(period, dict):
        errors.append(f"{source} period must be an object")
    else:
        if not _date(period.get("start_date")):
            errors.append(f"{source} period.start_date must be YYYY-MM-DD")
        if not _date(period.get("end_date")):
            errors.append(f"{source} period.end_date must be YYYY-MM-DD")
    findings = _finding_map(manifest, source, errors)
    errors.extend(_validate_criteria_levels(manifest, source))
    errors.extend(
        _validate_rows(
            manifest.get("criteria_evaluations"),
            source=source,
            row_name="criteria_evaluations",
            id_key="criterion_id",
            expected_ids=PROJECT_CRITERIA_IDS,
            findings=findings,
            real_evidence=real_evidence,
            failed_message="failed criterion",
            allowed_real_statuses={"passed", "failed", "blocked", "not_applicable"},
        )
    )
    errors.extend(
        _validate_rows(
            manifest.get("hook_v2_checks"),
            source=source,
            row_name="hook_v2_checks",
            id_key="check_id",
            expected_ids=HOOK_CHECK_IDS,
            findings=findings,
            real_evidence=real_evidence,
            failed_message="failed hook check",
            allowed_real_statuses={"passed", "failed", "blocked", "not_applicable"},
        )
    )
    errors.extend(
        _validate_rows(
            manifest.get("component_refactor_checks"),
            source=source,
            row_name="component_refactor_checks",
            id_key="component",
            expected_ids=COMPONENT_TARGETS,
            findings=findings,
            real_evidence=real_evidence,
            failed_message="failed component check",
            allowed_real_statuses={"passed", "failed", "blocked", "not_applicable"},
        )
    )
    errors.extend(
        _validate_rows(
            manifest.get("source_snapshots"),
            source=source,
            row_name="source_snapshots",
            id_key="snapshot_id",
            expected_ids=SOURCE_SNAPSHOT_IDS,
            findings=findings,
            real_evidence=real_evidence,
            failed_message="stale source snapshot",
            allowed_real_statuses={"current", "stale"},
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
            return ["WCAG 2.2 upgrade evidence path must be inside the repository"]
    else:
        relative = path.as_posix()
    expected = f"{REPORT_ROOT}/{run_id}/{MANIFEST_FILENAME}"
    if relative != expected:
        return [f"WCAG 2.2 upgrade evidence path must be {expected}"]
    if ".." in Path(relative).parts:
        return ["WCAG 2.2 upgrade evidence path must not traverse directories"]
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


def validate_ci_workflow(workflow: str | None = None) -> list[str]:
    workflow_text = (
        workflow if workflow is not None else CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    )
    errors: list[str] = []
    for snippet in (
        "wcag_2_2_upgrade_path: ${{ steps.filter.outputs.wcag_2_2_upgrade_path }}",
        "wcag-2-2-upgrade-path-validation:",
    ):
        if snippet not in workflow_text:
            errors.append(f".github/workflows/ci.yml missing {snippet}")
    filter_block = _filter_block(workflow_text, "wcag_2_2_upgrade_path")
    if not filter_block:
        errors.append(".github/workflows/ci.yml missing wcag_2_2_upgrade_path path filter")
    for snippet in (
        "wcag_2_2_upgrade_path:",
        "'packages/ui/**'",
        "'tools/wcag_2_2_upgrade/**'",
        "'scripts/validate_wcag_2_2_upgrade_path.py'",
        "'tests/test_wcag_2_2_upgrade_path.py'",
        "'docs/runbooks/wcag-2-2-upgrade-path.md'",
        "'reports/wcag-2-2-upgrade/**'",
        "'tools/a11y_audit/**'",
        "'scripts/validate_a11y_quarterly_audit.py'",
        "'.github/workflows/ci.yml'",
    ):
        if snippet not in filter_block:
            errors.append(
                f".github/workflows/ci.yml wcag_2_2_upgrade_path filter missing {snippet}"
            )
    job = _job_block(workflow_text, "wcag-2-2-upgrade-path-validation")
    if not job:
        errors.append(".github/workflows/ci.yml missing wcag-2-2-upgrade-path-validation job")
        return errors
    for snippet in (
        "needs.changes.outputs.wcag_2_2_upgrade_path == 'true'",
        "uv run python scripts/validate_wcag_2_2_upgrade_path.py",
        "uv run python scripts/validate_wcag_2_2_upgrade_path.py --evidence",
        "uv run pytest tests/test_wcag_2_2_upgrade_path.py -v",
        "pnpm --filter @opticloud/ui test -- src/hooks/useA11y.wcag22.test.tsx",
        "pnpm --filter @opticloud/ui test:a11y",
        "pnpm --filter @opticloud/ui typecheck",
    ):
        if snippet not in job:
            errors.append(f".github/workflows/ci.yml wcag 2.2 job missing {snippet}")
    if "continue-on-error" in job:
        errors.append("wcag-2-2-upgrade-path-validation must not use continue-on-error")
    return errors


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    example_manifest = load_json(EXAMPLE_MANIFEST_PATH)
    if not isinstance(contract, dict):
        return ["wcag_2_2_upgrade_contract.json must contain an object"]
    errors.extend(validate_contract(contract))
    if not isinstance(schema, dict):
        errors.append("wcag_2_2_upgrade_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_schema(schema))
    if not isinstance(example_manifest, dict):
        errors.append("wcag_2_2_upgrade_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_manifest(
                example_manifest,
                contract,
                source="wcag_2_2_upgrade_manifest.example.json",
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
        help="Optional redacted evidence under reports/wcag-2-2-upgrade/<run_id>/",
    )
    args = parser.parse_args(argv)
    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("WCAG 2.2 upgrade path OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
