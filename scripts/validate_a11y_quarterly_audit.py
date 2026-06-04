"""Validate Story 9.1 quarterly accessibility audit governance assets.

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
A11Y_DIR = REPO_ROOT / "tools" / "a11y_audit"
CONTRACT_PATH = A11Y_DIR / "quarterly_a11y_contract.json"
SCHEMA_PATH = A11Y_DIR / "quarterly_a11y_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = A11Y_DIR / "quarterly_a11y_manifest.example.json"
UI_PACKAGE_PATH = REPO_ROOT / "packages" / "ui" / "package.json"
UI_COMPONENTS_DIR = REPO_ROOT / "packages" / "ui" / "src" / "components"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

AUDIT_VERSION = "quarterly_a11y_audit_v1"
SOURCE_STORY = "9.1"
AUTOMATED_COMMAND = "pnpm --filter @opticloud/ui test:a11y"
UI_PACKAGE = "@opticloud/ui"
REPORT_ROOT = "reports/a11y-quarterly"
MANIFEST_FILENAME = "audit_manifest.json"
PROFILE_IDS = (
    "screen_reader",
    "keyboard_only",
    "high_contrast",
    "low_vision",
    "motor",
    "cognitive",
)
PERSONA_IDS = (
    "li_gong_curl",
    "lina_csv",
    "lao_zhang_excel",
    "chen_architect_sdk",
)
MANIFEST_ROOT_REQUIRED = {
    "source_story",
    "audit_version",
    "run_id",
    "example_only",
    "generated_by",
    "commit_sha",
    "quarter",
    "period",
    "automated_axe",
    "manual_sampling",
    "findings",
    "redaction_reviewed",
    "release_approved",
    "real_panel_completed",
    "third_party_audit_completed",
}
STATIC_COMPLETION_FLAGS = {
    "real_audit_passed",
    "real_quarterly_audit_completed",
    "real_panel_completed",
    "release_approved",
    "production_release_approved",
    "external_ticket_created",
    "third_party_audit_completed",
    "recruitment_completed",
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
    "participant_name",
    "participant_email",
    "email",
    "phone",
    "tenant_id",
    "customer_id",
    "user_id",
    "prompt",
    "provider_payload",
    "provider_request",
    "provider_response",
    "raw_browser_log",
    "browser_log",
}
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"tenant[_-]?id|customer[_-]?id|user[_-]?id|participant[_-]?(name|email)|"
    r"phone|cookie|prompt|provider[_-]?payload|provider[_-]?request|"
    r"provider[_-]?response|raw[_-]?browser[_-]?log|browser[_-]?log)([_-]|$)",
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
    "Windows absolute path": re.compile(r"^[A-Za-z]:[\\/]"),
    "POSIX absolute path": re.compile(r"^/[A-Za-z0-9_.-]"),
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


def discover_component_a11y_tests() -> list[str]:
    return sorted(
        path.relative_to(REPO_ROOT / "packages" / "ui").as_posix()
        for path in UI_COMPONENTS_DIR.glob("**/*.a11y.test.tsx")
    )


def validate_ui_a11y_script(
    package_json: dict[str, Any] | None = None,
    discovered_files: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    package_json = package_json or load_json(UI_PACKAGE_PATH)
    discovered_files = discovered_files or discover_component_a11y_tests()
    scripts = package_json.get("scripts")
    if not isinstance(scripts, dict):
        return ["packages/ui/package.json scripts must be an object"]
    test_a11y = scripts.get("test:a11y")
    if not isinstance(test_a11y, str):
        return ["packages/ui/package.json must define scripts.test:a11y"]
    if "vitest run" not in test_a11y:
        errors.append("packages/ui scripts.test:a11y must use vitest run")
    if "src/components/Tier1.a11y.test.tsx" not in test_a11y:
        errors.append("packages/ui scripts.test:a11y must include Tier1.a11y.test.tsx")
    for path in discovered_files:
        if path not in test_a11y:
            errors.append(f"packages/ui scripts.test:a11y missing committed a11y test {path}")
    return errors


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_values = {
        "audit_version": AUDIT_VERSION,
        "source_story": SOURCE_STORY,
        "nfr": "NFR-A",
        "wcag_scope": "WCAG 2.1 AA",
        "wcag_2_2_upgrade_story": "9.5",
    }
    for key, expected in expected_values.items():
        if contract.get(key) != expected:
            errors.append(f"quarterly_a11y_contract.json {key} must be {expected}")
    automated = contract.get("automated_gate")
    if not isinstance(automated, dict):
        errors.append("quarterly_a11y_contract.json automated_gate must be an object")
    else:
        if automated.get("package") != UI_PACKAGE:
            errors.append("quarterly_a11y_contract.json automated_gate.package drifted")
        if automated.get("command") != AUTOMATED_COMMAND:
            errors.append("quarterly_a11y_contract.json automated_gate.command drifted")
        if automated.get("test_script") != "test:a11y":
            errors.append("quarterly_a11y_contract.json automated_gate.test_script drifted")
        if automated.get("runner") != "vitest":
            errors.append("quarterly_a11y_contract.json automated_gate.runner must be vitest")
        if automated.get("expected_violations") != 0:
            errors.append("quarterly_a11y_contract.json expected_violations must be 0")
    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("quarterly_a11y_contract.json evidence must be an object")
    else:
        if evidence.get("report_directory") != REPORT_ROOT:
            errors.append("quarterly_a11y_contract.json evidence.report_directory drifted")
        if evidence.get("manifest_filename") != MANIFEST_FILENAME:
            errors.append("quarterly_a11y_contract.json evidence.manifest_filename drifted")
    profiles = contract.get("a11y_profiles")
    profile_ids = (
        [item.get("profile_id") for item in profiles] if isinstance(profiles, list) else []
    )
    if profile_ids != list(PROFILE_IDS):
        errors.append("quarterly_a11y_contract.json a11y_profiles must match canonical order")
    personas = contract.get("sub_personas")
    persona_ids = (
        [item.get("persona_id") for item in personas] if isinstance(personas, list) else []
    )
    if persona_ids != list(PERSONA_IDS):
        errors.append("quarterly_a11y_contract.json sub_personas must match canonical order")
    panel = contract.get("panel_sop")
    if not isinstance(panel, dict):
        errors.append("quarterly_a11y_contract.json panel_sop must be an object")
    else:
        if panel.get("cadence") != "quarterly":
            errors.append("quarterly_a11y_contract.json panel_sop.cadence must be quarterly")
        if panel.get("recruitment_lead_weeks") != 6:
            errors.append("quarterly_a11y_contract.json recruitment lead must be 6 weeks")
        if panel.get("participants_per_sub_persona_target") != 5:
            errors.append("quarterly_a11y_contract.json must target 5 participants per persona")
        if panel.get("backup_pool_multiplier") != 3:
            errors.append("quarterly_a11y_contract.json backup pool multiplier must be 3")
        if panel.get("finance_legal_approval_required") is not True:
            errors.append("quarterly_a11y_contract.json finance/legal approval must be required")
        if panel.get("disabled_user_panel_completion_claim") is not False:
            errors.append(
                "quarterly_a11y_contract.json must not claim disabled-user panel completion"
            )
    boundaries = contract.get("boundaries")
    if not isinstance(boundaries, dict):
        errors.append("quarterly_a11y_contract.json boundaries must be an object")
    else:
        for key in (
            "real_quarterly_audit_completed",
            "real_panel_completed",
            "third_party_audit_completed",
            "wcag_2_2_in_scope",
            "disabled_user_panel_completion_claim",
        ):
            if boundaries.get(key) is not False:
                errors.append(f"quarterly_a11y_contract.json boundaries.{key} must be false")
    if set(contract.get("disallowed_static_completion_claims", [])) != STATIC_COMPLETION_FLAGS:
        errors.append("quarterly_a11y_contract.json static completion flags drifted")
    errors.extend(validate_no_sensitive_values(contract, "quarterly_a11y_contract.json"))
    return errors


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != MANIFEST_ROOT_REQUIRED:
        errors.append("quarterly a11y schema root required fields drifted")
    profile_enum = schema.get("$defs", {}).get("profileId", {}).get("enum")
    if profile_enum != list(PROFILE_IDS):
        errors.append("quarterly a11y schema profile enum drifted")
    persona_enum = schema.get("$defs", {}).get("personaId", {}).get("enum")
    if persona_enum != list(PERSONA_IDS):
        errors.append("quarterly a11y schema persona enum drifted")
    ticket_required = _schema_required(schema, ["$defs", "ticketRef"])
    if ticket_required != {"ticket_id", "owner", "severity", "due_date", "status"}:
        errors.append("quarterly a11y schema ticketRef required fields drifted")
    errors.extend(validate_no_sensitive_values(schema, "quarterly_a11y_manifest.schema.json"))
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


def _validate_automated_axe(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    automated = manifest.get("automated_axe")
    if not isinstance(automated, dict):
        return [f"{source} automated_axe must be an object"]
    for key in (
        "package",
        "command",
        "executed",
        "status",
        "violation_count",
        "test_files",
        "finding_ids",
    ):
        if key not in automated:
            errors.append(f"{source} automated_axe missing {key}")
    if automated.get("package") != UI_PACKAGE:
        errors.append(f"{source} automated_axe.package must be {UI_PACKAGE}")
    if automated.get("command") != AUTOMATED_COMMAND:
        errors.append(f"{source} automated_axe.command must be {AUTOMATED_COMMAND}")
    if real_evidence:
        if automated.get("executed") is not True:
            errors.append(f"{source} real evidence automated_axe.executed must be true")
        if automated.get("status") not in {"passed", "failed"}:
            errors.append(f"{source} real evidence automated_axe.status must be passed or failed")
        if not isinstance(automated.get("violation_count"), int):
            errors.append(
                f"{source} real evidence automated_axe.violation_count must be an integer"
            )
    else:
        if automated.get("executed") is not False:
            errors.append(f"{source} example automated_axe.executed must be false")
        if automated.get("status") != "not_run_example":
            errors.append(f"{source} example automated_axe.status must be not_run_example")
        if automated.get("violation_count") is not None:
            errors.append(f"{source} example automated_axe.violation_count must be null")
    test_files = automated.get("test_files")
    if not isinstance(test_files, list) or not all(isinstance(item, str) for item in test_files):
        errors.append(f"{source} automated_axe.test_files must be a list of strings")
    elif real_evidence and sorted(test_files) != discover_component_a11y_tests():
        errors.append(f"{source} automated_axe.test_files must match committed test:a11y files")
    finding_ids = automated.get("finding_ids")
    if not isinstance(finding_ids, list):
        errors.append(f"{source} automated_axe.finding_ids must be a list")
        finding_ids = []
    for finding_id in finding_ids:
        if finding_id not in findings:
            errors.append(f"{source} automated_axe references unknown finding {finding_id}")
    failed = automated.get("status") == "failed" or (
        isinstance(automated.get("violation_count"), int) and automated["violation_count"] > 0
    )
    if failed and not finding_ids:
        errors.append(f"{source} failed automated_axe check must reference at least one finding")
    for finding_id in finding_ids:
        if finding_id in findings:
            errors.extend(
                _validate_ticket_refs(findings[finding_id], source=source, required=failed)
            )
    return errors


def _validate_manual_sampling(
    manifest: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    manual = manifest.get("manual_sampling")
    if not isinstance(manual, dict):
        return [f"{source} manual_sampling must be an object"]
    matrix = manual.get("matrix")
    if not isinstance(matrix, list):
        return [f"{source} manual_sampling.matrix must be a list"]
    expected = {(profile, persona) for profile in PROFILE_IDS for persona in PERSONA_IDS}
    seen: set[tuple[str, str]] = set()
    for cell in matrix:
        if not isinstance(cell, dict):
            errors.append(f"{source} manual_sampling cell must be an object")
            continue
        profile_id = cell.get("profile_id")
        persona_id = cell.get("persona_id")
        if profile_id not in PROFILE_IDS:
            errors.append(f"{source} manual_sampling has invalid profile_id {profile_id}")
        if persona_id not in PERSONA_IDS:
            errors.append(f"{source} manual_sampling has invalid persona_id {persona_id}")
        if isinstance(profile_id, str) and isinstance(persona_id, str):
            pair = (profile_id, persona_id)
            if pair in seen:
                errors.append(f"{source} manual_sampling duplicate cell {profile_id}/{persona_id}")
            seen.add(pair)
        status = cell.get("status")
        if real_evidence and status not in {"passed", "failed", "skipped_with_reason"}:
            errors.append(
                f"{source} real manual_sampling status invalid for {profile_id}/{persona_id}"
            )
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example manual_sampling status must be not_run_example")
        finding_ids = cell.get("finding_ids")
        if not isinstance(finding_ids, list):
            errors.append(f"{source} manual_sampling finding_ids must be a list")
            finding_ids = []
        for finding_id in finding_ids:
            if finding_id not in findings:
                errors.append(f"{source} manual_sampling references unknown finding {finding_id}")
        if status == "failed" and not finding_ids:
            errors.append(f"{source} failed manual_sampling check must reference a finding")
        for finding_id in finding_ids:
            if finding_id in findings:
                errors.extend(
                    _validate_ticket_refs(
                        findings[finding_id],
                        source=source,
                        required=status == "failed",
                    )
                )
    missing = expected - seen
    for profile_id, persona_id in sorted(missing):
        errors.append(f"{source} manual_sampling missing matrix cell {profile_id}/{persona_id}")
    extra = seen - expected
    for profile_id, persona_id in sorted(extra):
        errors.append(f"{source} manual_sampling unexpected matrix cell {profile_id}/{persona_id}")
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
        if manifest.get("real_panel_completed") is not True:
            errors.append(f"{source} real evidence real_panel_completed must be true")
    else:
        errors.extend(_validate_static_completion_claims(manifest, source))
    if manifest.get("third_party_audit_completed") is not False:
        errors.append(f"{source} third_party_audit_completed must be false for Story 9.1")
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
        _validate_automated_axe(
            manifest,
            findings,
            source=source,
            real_evidence=real_evidence,
        )
    )
    errors.extend(
        _validate_manual_sampling(
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
            return ["quarterly a11y evidence path must be inside the repository"]
    else:
        relative = path.as_posix()
    expected = f"{REPORT_ROOT}/{run_id}/{MANIFEST_FILENAME}"
    if relative != expected:
        return [f"quarterly a11y evidence path must be {expected}"]
    if ".." in Path(relative).parts:
        return ["quarterly a11y evidence path must not traverse directories"]
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
        "ui_a11y_audit: ${{ steps.filter.outputs.ui_a11y_audit }}",
        "ui-a11y-audit-validation:",
    ):
        if snippet not in workflow:
            errors.append(f".github/workflows/ci.yml missing {snippet}")

    filter_block = _filter_block(workflow, "ui_a11y_audit")
    if not filter_block:
        errors.append(".github/workflows/ci.yml missing ui_a11y_audit path filter")
    for snippet in (
        "ui_a11y_audit:",
        "'packages/ui/**'",
        "'tools/a11y_audit/**'",
        "'scripts/validate_a11y_quarterly_audit.py'",
        "'tests/test_a11y_quarterly_audit.py'",
        "'docs/runbooks/quarterly-a11y-audit.md'",
        "'reports/a11y-quarterly/**'",
    ):
        if snippet not in filter_block:
            errors.append(f".github/workflows/ci.yml ui_a11y_audit filter missing {snippet}")

    job = _job_block(workflow, "ui-a11y-audit-validation")
    if not job:
        errors.append(".github/workflows/ci.yml missing ui-a11y-audit-validation job")
        return errors
    for snippet in (
        "needs.changes.outputs.ui_a11y_audit == 'true'",
        "uv run python scripts/validate_a11y_quarterly_audit.py",
        "uv run python scripts/validate_a11y_quarterly_audit.py --evidence",
        "uv run pytest tests/test_a11y_quarterly_audit.py -v",
        "pnpm --filter @opticloud/ui test:a11y",
    ):
        if snippet not in job:
            errors.append(f".github/workflows/ci.yml ui-a11y job missing {snippet}")
    if "continue-on-error" in job:
        errors.append("ui-a11y-audit-validation must not use continue-on-error")
    return errors


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    example_manifest = load_json(EXAMPLE_MANIFEST_PATH)
    if not isinstance(contract, dict):
        return ["quarterly_a11y_contract.json must contain an object"]
    errors.extend(validate_contract(contract))
    if not isinstance(schema, dict):
        errors.append("quarterly_a11y_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_schema(schema))
    if not isinstance(example_manifest, dict):
        errors.append("quarterly_a11y_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_manifest(
                example_manifest,
                contract,
                source="quarterly_a11y_manifest.example.json",
                real_evidence=False,
            )
        )
    errors.extend(validate_ui_a11y_script())
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
        help="Optional redacted evidence under reports/a11y-quarterly/<run_id>/",
    )
    args = parser.parse_args(argv)
    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("quarterly a11y audit OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
