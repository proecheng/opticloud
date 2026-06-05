"""Validate Story 9.6 error i18n quarterly audit governance assets.

Default validation is static and runs the committed audit gates. Real redacted
operator evidence is validated only when passed explicitly with --evidence.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO_ROOT / "tools" / "error_i18n_audit"
CONTRACT_PATH = AUDIT_DIR / "error_i18n_audit_contract.json"
SCHEMA_PATH = AUDIT_DIR / "error_i18n_audit_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = AUDIT_DIR / "error_i18n_audit_manifest.example.json"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
ZH_DICTIONARY = REPO_ROOT / "packages" / "i18n" / "errors.zh-CN.yaml"
EN_DICTIONARY = REPO_ROOT / "packages" / "i18n" / "errors.en-US.yaml"
SINGLE_SOURCE_GATE = REPO_ROOT / "scripts" / "error_message_i18n_single_source.py"

SOURCE_STORY = "9.6"
AUDIT_VERSION = "error_i18n_quarterly_audit_v1"
RULE_ID = "error-message-i18n-single-source"
FG = "FG1.3"
NFR = "NFR-COMPLIANCE"
REPORT_ROOT = "reports/error-i18n-audit"
MANIFEST_FILENAME = "audit_manifest.json"
SCAN_CLASSES = (
    "typescript_problem_detail",
    "i18n_dictionary_parity",
    "solver_error_catalog",
    "billing_problem_details",
    "shared_rfc7807_helper",
    "sdk_preservation_fixture",
    "legacy_http_exception_register",
)
STRICT_ZERO_SCAN_CLASSES = {
    "typescript_problem_detail",
    "i18n_dictionary_parity",
    "solver_error_catalog",
}
SCAN_STATUSES = ("not_run_example", "passed", "failed", "missing_with_ticket", "stale")
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
    "scan_results",
    "findings",
    "redaction_reviewed",
    "release_approved",
    "real_quarterly_audit_completed",
    "real_full_codebase_migration_completed",
}
STATIC_COMPLETION_FLAGS = {
    "real_quarterly_audit_completed",
    "real_full_codebase_migration_completed",
    "real_external_ticket_created",
    "real_production_release_approved",
    "release_approved",
    "production_release_approved",
    "legacy_http_exception_migration_completed",
}
BILLING_SHARED_REQUIRED_KEYS = {
    "errors.400.billing_http_error",
    "errors.401.billing_http_error",
    "errors.402.billing_http_error",
    "errors.403.billing_http_error",
    "errors.404.billing_http_error",
    "errors.409.billing_http_error",
    "errors.422.billing_http_error",
    "errors.422.request_validation",
    "errors.503.billing_http_error",
}
LEGACY_SCAN_ROOTS = (REPO_ROOT / "apps", REPO_ROOT / "packages")
PRODUCTION_REMEDIATION_SCAN_ROOTS = (REPO_ROOT / "apps", REPO_ROOT / "packages")
PRODUCTION_REMEDIATION_SUFFIXES = {".py", ".ts", ".tsx"}
EXCLUDED_SOURCE_PARTS = {
    "__pycache__",
    ".next",
    "build",
    "dist",
    "node_modules",
    "tests",
}
EXCLUDED_SOURCE_NAME_PARTS = (".test.", ".spec.", ".stories.")
DYNAMIC_REMEDIATION_KEY_EXPANSIONS = {
    "errors.{status_code}.billing_http_error": BILLING_SHARED_REQUIRED_KEYS
    - {"errors.422.request_validation"},
    "errors.422.{result.status}": {
        "errors.422.infeasible",
        "errors.422.unbounded",
    },
    "errors.chat_sandbox.{error_code.value}": {
        "errors.chat_sandbox.invalid_input_path",
        "errors.chat_sandbox.llm_self_loop_blocked",
        "errors.chat_sandbox.logs_stream_deferred",
        "errors.chat_sandbox.network_disabled",
        "errors.chat_sandbox.result_budget_exceeded",
        "errors.chat_sandbox.unsupported_binary_payload",
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
    "raw_error_payload",
}
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"token|cookie|tenant[_-]?id|customer[_-]?id|user[_-]?id|account[_-]?id|"
    r"email|phone|prompt|provider[_-]?payload|provider[_-]?request|provider[_-]?response|"
    r"raw[_-]?log|raw[_-]?error[_-]?payload)([_-]|$)",
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
    "generic sk key": re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
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


def _ast_call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _parse_dictionary(path: Path) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    stack: list[tuple[int, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parts = tuple(part for _, part in stack) + (key,)
        if value == "":
            stack.append((indent, key))
            continue
        if len(parts) == 4 and parts[0] == "errors":
            error_key = f"errors.{parts[1]}.{parts[2]}"
            entries.setdefault(error_key, {})[parts[3]] = _unquote(value)
    return entries


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")
    return value


def dictionary_key_set() -> set[str]:
    zh = _parse_dictionary(ZH_DICTIONARY)
    en = _parse_dictionary(EN_DICTIONARY)
    return set(zh) & set(en)


def _dictionary_errors() -> list[str]:
    errors: list[str] = []
    zh = _parse_dictionary(ZH_DICTIONARY)
    en = _parse_dictionary(EN_DICTIONARY)
    if set(zh) != set(en):
        errors.append(
            "i18n dictionaries key parity drifted; "
            f"missing_en={sorted(set(zh) - set(en))}; missing_zh={sorted(set(en) - set(zh))}"
        )
    for path, entries in ((ZH_DICTIONARY, zh), (EN_DICTIONARY, en)):
        for key, fields in sorted(entries.items()):
            for field in ("title", "detail", "remediation"):
                if not fields.get(field, "").strip():
                    errors.append(f"{path.relative_to(REPO_ROOT).as_posix()} {key}.{field} missing")
    return errors


def discover_solver_catalog_keys() -> list[str]:
    path = REPO_ROOT / "apps" / "solver-orchestrator" / "src" / "solver_orchestrator" / "error_catalog.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.keyword)
            and node.arg == "remediation_hint_key"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            keys.add(node.value.value)
    return sorted(keys)


def discover_sdk_fixture_keys() -> list[str]:
    path = REPO_ROOT / "tests" / "fixtures" / "sdk-rfc7807-preservation.json"
    if not path.exists():
        return []
    data = load_json(path)
    keys: set[str] = set()
    for _, value in _walk_values(data):
        if isinstance(value, dict):
            key = value.get("remediation_hint_key")
            if isinstance(key, str):
                keys.add(key)
    return sorted(keys)


def _is_production_source(path: Path) -> bool:
    if path.suffix not in PRODUCTION_REMEDIATION_SUFFIXES:
        return False
    relative_parts = path.relative_to(REPO_ROOT).parts
    if any(part in EXCLUDED_SOURCE_PARTS for part in relative_parts):
        return False
    return not any(part in path.name for part in EXCLUDED_SOURCE_NAME_PARTS)


def _production_source_paths(root: Path | None = None) -> list[Path]:
    base = root or REPO_ROOT
    paths: list[Path] = []
    for scan_root in PRODUCTION_REMEDIATION_SCAN_ROOTS:
        candidate_root = scan_root if root is None else base
        if not candidate_root.exists():
            continue
        for path in candidate_root.rglob("*"):
            if path.is_file() and _is_production_source(path):
                paths.append(path)
        if root is not None:
            break
    return sorted(set(paths))


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _joined_string_template(node: ast.JoinedStr) -> str:
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        elif isinstance(value, ast.FormattedValue):
            source = ast.unparse(value.value)
            parts.append("{" + source + "}")
    return "".join(parts)


def _remediation_key_values_from_python(
    path: Path,
    source: str | None = None,
) -> list[tuple[int, str, bool]]:
    tree = ast.parse(source if source is not None else path.read_text(encoding="utf-8"))
    values: list[tuple[int, str, bool]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "remediation_hint_key":
            static_value = _constant_string(node.value)
            if static_value is not None:
                values.append((node.lineno, static_value, False))
            elif isinstance(node.value, ast.JoinedStr):
                values.append((node.lineno, _joined_string_template(node.value), True))
        elif isinstance(node, ast.Dict):
            for key_node, value_node in zip(node.keys, node.values, strict=False):
                if _constant_string(key_node) != "remediation_hint_key":
                    continue
                static_value = _constant_string(value_node)
                if static_value is not None:
                    values.append((value_node.lineno, static_value, False))
                elif isinstance(value_node, ast.JoinedStr):
                    values.append((value_node.lineno, _joined_string_template(value_node), True))
    return values


def _remediation_key_values_from_text(
    path: Path,
    source: str | None = None,
) -> list[tuple[int, str, bool]]:
    values: list[tuple[int, str, bool]] = []
    pattern = re.compile(
        r"remediation_hint_key\s*:\s*([\"'`])([^\"'`]+)\1|"
        r"remediationHintKey\s*:\s*([\"'`])([^\"'`]+)\3"
    )
    text = source if source is not None else path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in pattern.finditer(line):
            value = match.group(2) or match.group(4)
            values.append((line_number, value, "{" in value or "${" in value))
    return values


def discover_production_remediation_keys(root: Path | None = None) -> dict[str, Any]:
    static_keys: dict[str, list[str]] = {}
    dynamic_templates: dict[str, list[str]] = {}
    for path in _production_source_paths(root):
        try:
            source = path.read_text(encoding="utf-8")
            if "remediation_hint_key" not in source and "remediationHintKey" not in source:
                continue
            if path.suffix == ".py":
                discovered = _remediation_key_values_from_python(path, source)
            else:
                discovered = _remediation_key_values_from_text(path, source)
        except SyntaxError:
            continue
        for line_number, value, dynamic in discovered:
            location = f"{path.relative_to(REPO_ROOT).as_posix()}:{line_number}"
            if dynamic:
                dynamic_templates.setdefault(value, []).append(location)
            else:
                static_keys.setdefault(value, []).append(location)
    return {
        "static_keys": {key: sorted(locations) for key, locations in sorted(static_keys.items())},
        "dynamic_templates": {
            key: sorted(locations) for key, locations in sorted(dynamic_templates.items())
        },
    }


def validate_production_remediation_keys(
    keys: set[str],
    *,
    discovered: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    remediation_keys = discovered or discover_production_remediation_keys()
    static_keys = remediation_keys.get("static_keys", {})
    dynamic_templates = remediation_keys.get("dynamic_templates", {})
    if not isinstance(static_keys, dict) or not isinstance(dynamic_templates, dict):
        return ["production remediation key discovery returned invalid shape"]

    for key, locations in sorted(static_keys.items()):
        if not str(key).startswith("errors."):
            errors.append(f"production remediation key {key} at {locations} must start with errors.")
        elif key not in keys:
            errors.append(f"production remediation key {key} at {locations} missing from dictionaries")

    for template, locations in sorted(dynamic_templates.items()):
        if not str(template).startswith("errors."):
            errors.append(
                f"production dynamic remediation key {template} at {locations} "
                "must start with errors."
            )
            continue
        expanded = DYNAMIC_REMEDIATION_KEY_EXPANSIONS.get(template)
        if expanded is None:
            errors.append(
                f"production dynamic remediation key {template} at {locations} "
                "is not an approved bounded template"
            )
            continue
        for key in sorted(expanded):
            if key not in keys:
                errors.append(
                    f"production dynamic remediation key {template} expands to {key}, "
                    "which is missing from dictionaries"
                )
    return errors


def validate_key_sets(keys: set[str]) -> list[str]:
    errors: list[str] = []
    for key in discover_solver_catalog_keys():
        if key not in keys:
            errors.append(f"solver catalog key {key} missing from packages/i18n dictionaries")
    for key in discover_sdk_fixture_keys():
        if key not in keys:
            errors.append(f"SDK fixture key {key} missing from packages/i18n dictionaries")
    for key in sorted(BILLING_SHARED_REQUIRED_KEYS):
        if key not in keys:
            errors.append(f"billing/shared key {key} missing from packages/i18n dictionaries")
    errors.extend(validate_production_remediation_keys(keys))
    return errors


def _single_source_gate_errors() -> list[str]:
    spec = importlib.util.spec_from_file_location("error_message_i18n_single_source", SINGLE_SOURCE_GATE)
    if spec is None or spec.loader is None:
        return [f"{RULE_ID} gate cannot be loaded"]
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.validate_repository(REPO_ROOT))


def validate_committed_i18n_state() -> list[str]:
    errors: list[str] = []
    errors.extend(_single_source_gate_errors())
    errors.extend(_dictionary_errors())
    errors.extend(validate_key_sets(dictionary_key_set()))
    return errors


def discover_legacy_http_exception_register() -> dict[str, Any]:
    by_file: dict[str, int] = {}
    for root in LEGACY_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "tests" in path.parts or "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            count = 0
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if _ast_call_name(node.func) != "HTTPException":
                    continue
                for keyword in node.keywords:
                    if (
                        keyword.arg == "detail"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        count += 1
            if count:
                by_file[path.relative_to(REPO_ROOT).as_posix()] = count
    return {
        "total_count": sum(by_file.values()),
        "by_file": dict(sorted(by_file.items())),
    }


def discover_repo_state() -> dict[str, Any]:
    return {
        "typescript_single_source_gate": {
            "rule_id": RULE_ID,
            "path": "scripts/error_message_i18n_single_source.py",
            "source_roots": ["apps/web/src", "packages/ui/src", "packages/shared-ts/src"],
        },
        "i18n_dictionaries": {
            "paths": ["packages/i18n/errors.zh-CN.yaml", "packages/i18n/errors.en-US.yaml"],
            "key_count": len(dictionary_key_set()),
        },
        "solver_error_catalog": {
            "path": "apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py",
            "remediation_hint_keys": discover_solver_catalog_keys(),
        },
        "billing_problem_details": {
            "paths": [
                "apps/billing-service/src/billing_service/problem_details.py",
                "apps/billing-service/src/billing_service/main.py",
            ],
            "required_keys": sorted(BILLING_SHARED_REQUIRED_KEYS),
        },
        "shared_rfc7807_helper": {
            "path": "packages/shared-py/opticloud_shared/errors/rfc7807.py",
        },
        "sdk_preservation_fixture": {
            "path": "tests/fixtures/sdk-rfc7807-preservation.json",
            "remediation_hint_keys": discover_sdk_fixture_keys(),
        },
        "legacy_http_exception_register": discover_legacy_http_exception_register(),
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_values: dict[str, Any] = {
        "source_story": SOURCE_STORY,
        "audit_version": AUDIT_VERSION,
        "rule_id": RULE_ID,
        "fg": FG,
        "nfr": NFR,
        "standard_cadence": "quarterly",
    }
    for key, expected in expected_values.items():
        if contract.get(key) != expected:
            errors.append(f"error_i18n_audit_contract.json {key} must be {expected}")
    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("error_i18n_audit_contract.json evidence must be an object")
    else:
        if evidence.get("report_directory") != REPORT_ROOT:
            errors.append("error_i18n_audit_contract.json evidence.report_directory drifted")
        if evidence.get("manifest_filename") != MANIFEST_FILENAME:
            errors.append("error_i18n_audit_contract.json evidence.manifest_filename drifted")
    scan_classes = contract.get("scan_classes")
    if not isinstance(scan_classes, list):
        errors.append("error_i18n_audit_contract.json scan_classes must be a list")
        scan_classes = []
    if [item.get("scan_class") for item in scan_classes if isinstance(item, dict)] != list(SCAN_CLASSES):
        errors.append("error_i18n_audit_contract.json scan_classes must match Story 9.6")
    for item in scan_classes:
        if not isinstance(item, dict):
            errors.append("error_i18n_audit_contract.json scan class item must be object")
            continue
        for key in ("scan_class", "owner", "scope", "hardcoded_count_required_zero"):
            if key not in item:
                errors.append(f"error_i18n_audit_contract.json scan class missing {key}")
    observed = contract.get("observed_repo_state")
    if not isinstance(observed, dict):
        errors.append("error_i18n_audit_contract.json observed_repo_state must be object")
    elif observed != discover_repo_state():
        errors.append("error_i18n_audit_contract.json observed_repo_state drifted")
    boundaries = contract.get("boundaries")
    if not isinstance(boundaries, dict):
        errors.append("error_i18n_audit_contract.json boundaries must be object")
    else:
        for key in (
            "full_backend_runtime_migration_claimed",
            "real_quarterly_audit_completed",
            "real_external_ticket_created",
            "production_release_approved",
            "legacy_public_http_exception_migration_completed",
        ):
            if boundaries.get(key) is not False:
                errors.append(f"error_i18n_audit_contract.json boundaries.{key} must be false")
    if set(contract.get("disallowed_static_completion_claims", [])) != STATIC_COMPLETION_FLAGS:
        errors.append("error_i18n_audit_contract.json static completion flags drifted")
    errors.extend(validate_no_sensitive_values(contract, "error_i18n_audit_contract.json"))
    return errors


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != MANIFEST_ROOT_REQUIRED:
        errors.append("Error i18n audit schema root required fields drifted")
    scan_enum = schema.get("$defs", {}).get("scanClass", {}).get("enum")
    if scan_enum != list(SCAN_CLASSES):
        errors.append("Error i18n audit schema scan class enum drifted")
    status_enum = schema.get("$defs", {}).get("scanStatus", {}).get("enum")
    if status_enum != list(SCAN_STATUSES):
        errors.append("Error i18n audit schema status enum drifted")
    ticket_required = _schema_required(schema, ["$defs", "ticketRef"])
    if ticket_required != {"ticket_id", "owner", "severity", "due_date", "status"}:
        errors.append("Error i18n audit schema ticketRef required fields drifted")
    errors.extend(validate_no_sensitive_values(schema, "error_i18n_audit_manifest.schema.json"))
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
    finding_id = finding.get("finding_id", "<unknown>")
    ticket_refs = finding.get("ticket_refs")
    if not isinstance(ticket_refs, list):
        return [f"{source} finding {finding_id} ticket_refs must be a list"]
    if required and not ticket_refs:
        return [f"{source} finding {finding_id} must include ticket_refs"]
    errors: list[str] = []
    for ticket in ticket_refs:
        if not isinstance(ticket, dict):
            errors.append(f"{source} finding {finding_id} ticket ref must be object")
            continue
        for key in ("ticket_id", "owner", "severity", "due_date", "status"):
            if key not in ticket:
                errors.append(f"{source} finding {finding_id} ticket missing {key}")
        if ticket.get("severity") != finding.get("severity"):
            errors.append(f"{source} finding {finding_id} ticket severity must match finding")
    return errors


def _validate_finding_refs(
    ids: Any,
    findings: dict[str, dict[str, Any]],
    *,
    source: str,
    failed: bool,
) -> list[str]:
    errors: list[str] = []
    if ids is None:
        ids = []
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


def _scan_result_map(manifest: dict[str, Any], source: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    scan_results = manifest.get("scan_results")
    if not isinstance(scan_results, list):
        errors.append(f"{source} scan_results must be a list")
        return {}
    by_class: dict[str, dict[str, Any]] = {}
    for item in scan_results:
        if not isinstance(item, dict):
            errors.append(f"{source} scan result must be an object")
            continue
        scan_class = item.get("scan_class")
        if scan_class not in SCAN_CLASSES:
            errors.append(f"{source} invalid scan_class {scan_class}")
            continue
        if scan_class in by_class:
            errors.append(f"{source} duplicate scan_class {scan_class}")
        by_class[str(scan_class)] = item
        for key in ("scan_class", "status", "hardcoded_error_string_count", "finding_ids"):
            if key not in item:
                errors.append(f"{source} scan result {scan_class} missing {key}")
    for scan_class in SCAN_CLASSES:
        if scan_class not in by_class:
            errors.append(f"{source} missing scan result {scan_class}")
    return by_class


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
    if manifest.get("cadence_mode") != "quarterly":
        errors.append(f"{source} cadence_mode must be quarterly")
    if manifest.get("example_only") is not (not real_evidence):
        expected = "false" if real_evidence else "true"
        errors.append(f"{source} example_only must be {expected}")
    if real_evidence:
        if manifest.get("redaction_reviewed") is not True:
            errors.append(f"{source} real evidence redaction_reviewed must be true")
        if manifest.get("real_quarterly_audit_completed") is not True:
            errors.append(f"{source} real evidence real_quarterly_audit_completed must be true")
    else:
        errors.extend(_validate_static_completion_claims(manifest, source))
        if manifest.get("redaction_reviewed") is not False:
            errors.append(f"{source} example redaction_reviewed must be false")
        if manifest.get("release_approved") is not False:
            errors.append(f"{source} example release_approved must be false")
    if manifest.get("real_full_codebase_migration_completed") is not False:
        errors.append(f"{source} real_full_codebase_migration_completed must remain false")

    period = manifest.get("period")
    if not isinstance(period, dict):
        errors.append(f"{source} period must be an object")
    else:
        if not _date(period.get("start_date")):
            errors.append(f"{source} period.start_date must be YYYY-MM-DD")
        if not _date(period.get("end_date")):
            errors.append(f"{source} period.end_date must be YYYY-MM-DD")

    findings = _finding_map(manifest, source, errors)
    scan_results = _scan_result_map(manifest, source, errors)
    for scan_class, result in scan_results.items():
        status = result.get("status")
        if status not in SCAN_STATUSES:
            errors.append(f"{source} scan result {scan_class} status invalid")
        if not real_evidence and status != "not_run_example":
            errors.append(f"{source} example scan result {scan_class} status must be not_run_example")
        if real_evidence and status == "not_run_example":
            errors.append(f"{source} real scan result {scan_class} must not be not_run_example")
        count = result.get("hardcoded_error_string_count")
        if not isinstance(count, int) or count < 0:
            errors.append(f"{source} scan result {scan_class} hardcoded count must be nonnegative int")
        elif real_evidence and scan_class in STRICT_ZERO_SCAN_CLASSES and count != 0:
            errors.append(f"{source} scan result {scan_class} hardcoded_error_string_count must be 0")
        legacy_count = result.get("legacy_public_http_exception_count")
        failed = status in {"failed", "missing_with_ticket", "stale"}
        if real_evidence and scan_class == "legacy_http_exception_register":
            if not isinstance(legacy_count, int):
                errors.append(f"{source} legacy_http_exception_register must report count")
            elif legacy_count > 0:
                failed = True
        errors.extend(
            _validate_finding_refs(
                result.get("finding_ids"),
                findings,
                source=f"{source} scan result {scan_class}",
                failed=failed,
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
            return ["Error i18n audit evidence path must be inside the repository"]
    else:
        relative = path.as_posix()
    expected = f"{REPORT_ROOT}/{run_id}/{MANIFEST_FILENAME}"
    if relative != expected:
        return [f"Error i18n audit evidence path must be {expected}"]
    if ".." in Path(relative).parts:
        return ["Error i18n audit evidence path must not traverse directories"]
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
        "error_i18n_audit: ${{ steps.filter.outputs.error_i18n_audit }}",
        "error-i18n-audit-validation:",
    ):
        if snippet not in workflow:
            errors.append(f".github/workflows/ci.yml missing {snippet}")
    filter_block = _filter_block(workflow, "error_i18n_audit")
    if not filter_block:
        errors.append(".github/workflows/ci.yml missing error_i18n_audit path filter")
    for snippet in (
        "error_i18n_audit:",
        "'tools/error_i18n_audit/**'",
        "'scripts/validate_error_i18n_audit.py'",
        "'tests/test_error_i18n_audit.py'",
        "'docs/runbooks/error-i18n-audit.md'",
        "'reports/error-i18n-audit/**'",
        "'packages/i18n/**'",
        "'scripts/error_message_i18n_single_source.py'",
        "'tests/test_error_i18n_single_source.py'",
        "'apps/web/src/**'",
        "'packages/ui/src/**'",
        "'packages/shared-ts/src/**'",
        "'packages/*/src/**/*.py'",
        "'packages/*/src/**/*.ts'",
        "'packages/*/src/**/*.tsx'",
        "'packages/shared-py/**/*.py'",
        "'apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py'",
        "'apps/solver-orchestrator/src/solver_orchestrator/error_responses.py'",
        "'apps/billing-service/src/billing_service/problem_details.py'",
        "'apps/billing-service/src/billing_service/main.py'",
        "'apps/*/src/**/*.py'",
        "'packages/shared-py/opticloud_shared/errors/**'",
        "'tests/fixtures/sdk-rfc7807-preservation.json'",
        "'.github/workflows/ci.yml'",
    ):
        if snippet not in filter_block:
            errors.append(f".github/workflows/ci.yml error_i18n_audit filter missing {snippet}")
    job = _job_block(workflow, "error-i18n-audit-validation")
    if not job:
        errors.append(".github/workflows/ci.yml missing error-i18n-audit-validation job")
        return errors
    for snippet in (
        "needs.changes.outputs.error_i18n_audit == 'true'",
        "uv run python scripts/validate_error_i18n_audit.py",
        "uv run python scripts/validate_error_i18n_audit.py --evidence",
        "uv run pytest tests/test_error_i18n_audit.py -v",
        "uv run python scripts/error_message_i18n_single_source.py",
        "uv run pytest tests/test_error_i18n_single_source.py -v",
    ):
        if snippet not in job:
            errors.append(f".github/workflows/ci.yml error i18n audit job missing {snippet}")
    if "continue-on-error" in job:
        errors.append("error-i18n-audit-validation must not use continue-on-error")
    return errors


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    example_manifest = load_json(EXAMPLE_MANIFEST_PATH)
    if not isinstance(contract, dict):
        return ["error_i18n_audit_contract.json must contain an object"]
    errors.extend(validate_contract(contract))
    if not isinstance(schema, dict):
        errors.append("error_i18n_audit_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_schema(schema))
    if not isinstance(example_manifest, dict):
        errors.append("error_i18n_audit_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_manifest(
                example_manifest,
                contract,
                source="error_i18n_audit_manifest.example.json",
                real_evidence=False,
            )
        )
    errors.extend(validate_committed_i18n_state())
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
        help="Optional redacted evidence under reports/error-i18n-audit/<run_id>/",
    )
    args = parser.parse_args(argv)
    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("error i18n audit OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
