"""Validate Story 5.A.0c static Saga cross-epic dry-run assets."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

from opticloud_shared.saga.contract_fixtures import (
    CONTRACT_FIXTURE_MANIFEST,
    SAGA_CONTRACT_VERSION,
    SagaFixtureManifest,
    validate_contract_fixture_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DRYRUN_DIR = REPO_ROOT / "tools" / "saga_cross_epic_dryrun"
PLAN_PATH = DRYRUN_DIR / "dryrun_plan.json"
SIGNOFF_PATH = DRYRUN_DIR / "owner_signoff.example.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "saga-cross-epic-dryrun.md"

STORY_KEY = "5-a-0c-saga-cross-epic-dryrun"
UPSTREAM_STORIES = ["5-a-0a-saga-implementation", "5-a-0b-saga-contract-fixtures"]
REQUIRED_BLOCKING_ROLES = ["Billing Lead", "Solver Lead", "SRE"]
CONSULTED_ROLES = ["Provider Interface Lead"]
ALLOWED_ROLES = frozenset(REQUIRED_BLOCKING_ROLES + CONSULTED_ROLES)
DECISION = "standard_first_simplified_fallback"
CURRENT_TARGET = "standard_path"
ARTIFACT_ROOT = "tools/saga_cross_epic_dryrun/"
EXPECTED_ARTIFACT_PATHS = [
    "tools/saga_cross_epic_dryrun/dryrun_plan.json",
    "tools/saga_cross_epic_dryrun/owner_signoff.example.json",
]
EXPECTED_RUNBOOK_PATH = "docs/runbooks/saga-cross-epic-dryrun.md"
REQUIRED_OWNER_FOCUS = {
    "Billing Lead": {
        "ledger_delta_matches_contract_fixtures",
        "idempotency_same_body_replay_and_conflict_semantics",
        "outbox_event_count_matches_state_transitions",
        "paused_by_budget_remains_non_executable_gap",
    },
    "Solver Lead": {
        "no_billing_header_skips_reserve_and_finalize",
        "reserve_success_then_solve_success_finalizes_success",
        "reserve_failure_returns_422_without_solve_or_finalize",
        "solve_failure_finalizes_failure",
        "finalize_failure_preserves_solver_result_and_records_billing_failure",
    },
    "SRE": {
        "timeout_and_retry_contract_is_visible",
        "outbox_relayer_observability_boundary_is_documented",
        "reconciler_and_incident_path_are_named_without_running_services",
        "rollback_scenarios_have_owner_accountability",
    },
    "Provider Interface Lead": {
        "future_provider_interface_compatibility",
        "cost_telemetry_hook_placeholder_stays_schema_only",
    },
}

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
BEARER_PATTERN = re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE)
SECRET_PATTERN = re.compile(
    r"\b(api[_-]?key|token|secret|password|private[_-]?key)\b", re.IGNORECASE
)
RAW_URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)
TENANT_USER_PATTERN = re.compile(
    r"\b(tenant[_-]?id|user[_-]?id|account[_-]?id)\b|"
    r"\b(?:tenant|user|account)-[A-Za-z0-9][A-Za-z0-9_-]*\b",
    re.IGNORECASE,
)
PROMPT_VALUE_PATTERN = re.compile(
    r"\b(raw\s+prompt|customer\s+input|raw\s+input|raw\s+optimization\s+payload)\b",
    re.IGNORECASE,
)
PROMPT_KEY_PATTERN = re.compile(r"(^|[_-])(prompt|input|payload)([_-]|$)", re.IGNORECASE)
APPROVAL_WORD_PATTERN = re.compile(r"\b(approved|signed|complete|passed|pass)\b", re.IGNORECASE)
FAKE_COMPLETION_PATTERN = re.compile(
    r"\b(approved|signed|complete|passed|ci\s+passed|production\s+dry[- ]?run)\b",
    re.IGNORECASE,
)


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


def _value(value: Any) -> Any:
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return enum_value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return value


def _fixture_summary_payload(manifest: SagaFixtureManifest) -> dict[str, Any]:
    category_counts = Counter(str(fixture.category) for fixture in manifest.fixtures)
    fixtures = [
        {
            "fixture_id": fixture.fixture_id,
            "category": str(fixture.category),
            "executable": fixture.executable,
            "expected_final_state": _value(fixture.expected_final_state),
            "expected_ledger_delta": _value(fixture.expected_ledger_delta),
            "expected_outbox_count": fixture.expected_outbox_count,
            "idempotency_case": fixture.idempotency_case,
            "unsupported_state": fixture.unsupported_state,
            "expected_body_hash": fixture.expected_body_hash,
        }
        for fixture in manifest.fixtures
    ]
    return {
        "version": manifest.version,
        "generated_at": _value(manifest.generated_at),
        "category_minimums": {
            str(category): minimum
            for category, minimum in sorted(manifest.category_minimums.items())
        },
        "total_fixtures": len(manifest.fixtures),
        "executable_fixtures": len(manifest.executable_fixtures),
        "category_counts": {
            category: category_counts[category] for category in sorted(category_counts)
        },
        "fixtures": fixtures,
    }


def build_fixture_manifest_summary() -> dict[str, Any]:
    validate_contract_fixture_manifest(CONTRACT_FIXTURE_MANIFEST)
    payload = _fixture_summary_payload(CONTRACT_FIXTURE_MANIFEST)
    return {
        "version": SAGA_CONTRACT_VERSION,
        "sha256": canonical_sha256(payload),
        "total_fixtures": payload["total_fixtures"],
        "executable_fixtures": payload["executable_fixtures"],
        "category_counts": payload["category_counts"],
    }


def _walk_values(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    values = [(path, value)]
    if isinstance(value, dict):
        for key, nested in value.items():
            values.extend(_walk_values(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            values.extend(_walk_values(nested, f"{path}[{index}]"))
    return values


def _normalize_key(key: str) -> str:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()
    return normalized.replace("-", "_")


def validate_no_sensitive_values(data: Any, source: str) -> list[str]:
    errors: list[str] = []
    for path, value in _walk_values(data):
        if isinstance(value, dict):
            for key in value:
                normalized_key = _normalize_key(str(key))
                if EMAIL_PATTERN.search(str(key)):
                    errors.append(f"{source} contains forbidden email at {path}.{key}")
                if TENANT_USER_PATTERN.search(normalized_key):
                    errors.append(
                        f"{source} contains forbidden tenant/user identifier at {path}.{key}"
                    )
                if PROMPT_KEY_PATTERN.search(normalized_key):
                    errors.append(f"{source} contains forbidden prompt-like key at {path}.{key}")
                if SECRET_PATTERN.search(normalized_key):
                    errors.append(f"{source} contains forbidden secret-like key at {path}.{key}")
        if isinstance(value, str):
            if EMAIL_PATTERN.search(value):
                errors.append(f"{source} contains forbidden email at {path}")
            if BEARER_PATTERN.search(value):
                errors.append(f"{source} contains forbidden bearer token at {path}")
            if RAW_URL_PATTERN.search(value):
                errors.append(f"{source} contains forbidden raw URL host at {path}")
            if TENANT_USER_PATTERN.search(value):
                errors.append(f"{source} contains forbidden tenant/user identifier at {path}")
            if PROMPT_VALUE_PATTERN.search(value):
                errors.append(f"{source} contains forbidden prompt-like value at {path}")
    return errors


def validate_no_fake_completion_claims(data: Any, source: str) -> list[str]:
    errors: list[str] = []
    for path, value in _walk_values(data):
        if isinstance(value, str) and FAKE_COMPLETION_PATTERN.search(value):
            errors.append(f"{source} contains forbidden fake completion claim at {path}")
    return errors


def validate_runbook_text(text: str) -> list[str]:
    return validate_no_sensitive_values({"runbook": text}, "runbook")


def _validate_object_fields(
    data: dict[str, Any],
    *,
    required: set[str],
    allowed: set[str],
    source: str,
) -> list[str]:
    errors: list[str] = []
    for key in sorted(required - set(data)):
        errors.append(f"{source} missing required field {key}")
    for key in sorted(set(data) - allowed):
        errors.append(f"{source} unexpected field {key}")
    return errors


def _validate_artifact_path(path_value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(path_value, str):
        return ["artifact path must be a string"]
    path = Path(path_value)
    if (
        path.is_absolute()
        or path_value.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:[\\/]", path_value)
    ):
        errors.append(f"artifact path must be repository-relative: {path_value}")
    if ".." in path.parts:
        errors.append(f"artifact path must not traverse directories: {path_value}")
    if not path_value.startswith(ARTIFACT_ROOT):
        errors.append(f"artifact path must stay under {ARTIFACT_ROOT}: {path_value}")
    return errors


def _validate_runbook_path(path_value: Any) -> list[str]:
    if path_value != EXPECTED_RUNBOOK_PATH:
        return [f"runbook_path must be {EXPECTED_RUNBOOK_PATH}"]
    return []


def _owner_entries(owner_map: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(owner_map, list):
        return {}, ["owner_review_map must be a list"]
    entries: dict[str, dict[str, Any]] = {}
    for entry in owner_map:
        if not isinstance(entry, dict):
            errors.append("owner_review_map entries must be objects")
            continue
        role = entry.get("role")
        if not isinstance(role, str):
            errors.append("owner_review_map entry role must be a string")
            continue
        if role not in ALLOWED_ROLES:
            errors.append(f"owner role {role!r} is not allowed")
        if role in entries:
            errors.append(f"owner role {role!r} is duplicated")
        entries[role] = entry
    return entries, errors


def _validate_owner_map(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("required_blocking_signoff_roles") != REQUIRED_BLOCKING_ROLES:
        errors.append("required_blocking_signoff_roles must be Billing Lead, Solver Lead, SRE")

    entries, entry_errors = _owner_entries(plan.get("owner_review_map"))
    errors.extend(entry_errors)
    for role in REQUIRED_BLOCKING_ROLES:
        entry = entries.get(role)
        if entry is None:
            errors.append(f"{role} owner entry is required")
            continue
        if entry.get("blocking") is not True:
            errors.append(f"{role} owner entry must be blocking")
    provider = entries.get("Provider Interface Lead")
    if provider is None:
        errors.append("Provider Interface Lead owner entry is required")
    elif provider.get("blocking") is not False:
        errors.append("Provider Interface Lead owner entry must be non-blocking")

    billing_categories = set(entries.get("Billing Lead", {}).get("fixture_categories", []))
    if not {"charge", "refund", "rollback", "idempotency"}.issubset(billing_categories):
        errors.append(
            "Billing Lead fixture_categories must cover charge/refund/rollback/idempotency"
        )
    sre_categories = set(entries.get("SRE", {}).get("fixture_categories", []))
    if not {"timeout", "budget_pause_stub"}.issubset(sre_categories):
        errors.append("SRE fixture_categories must cover timeout and budget_pause_stub")
    for role, required_focus in REQUIRED_OWNER_FOCUS.items():
        focus = set(entries.get(role, {}).get("review_focus", []))
        missing = sorted(required_focus - focus)
        if missing:
            errors.append(f"{role} review_focus must include {', '.join(missing)}")
    return errors


def _validate_fixture_manifest(
    fixture_manifest: Any, expected_summary: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if not isinstance(fixture_manifest, dict):
        return ["fixture_manifest must be an object"]
    if fixture_manifest.get("version") != expected_summary["version"]:
        errors.append("fixture manifest version does not match 5.A.0b public API")
    if fixture_manifest.get("sha256") != expected_summary["sha256"]:
        errors.append("fixture manifest sha256 does not match 5.A.0b public API")
    if fixture_manifest.get("total_fixtures") != expected_summary["total_fixtures"]:
        errors.append("fixture total_fixtures does not match 5.A.0b public API")
    if fixture_manifest.get("executable_fixtures") != expected_summary["executable_fixtures"]:
        errors.append("fixture executable_fixtures does not match 5.A.0b public API")
    if fixture_manifest.get("category_counts") != expected_summary["category_counts"]:
        errors.append("fixture category_counts do not match 5.A.0b public API")
    return errors


def _validate_claims(claims: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(claims, dict):
        return ["claims must be an object"]
    for key in (
        "real_committee_approval",
        "production_dryrun",
        "live_services_executed",
        "ci_passed",
        "release_approved",
    ):
        if claims.get(key) is not False:
            errors.append(f"{key} must be false")
    return errors


def _validate_decision(decision_record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(decision_record, dict):
        return ["decision_record must be an object"]
    if decision_record.get("decision") != DECISION:
        errors.append(f"decision must be {DECISION}")
    if decision_record.get("current_implementation_target") != CURRENT_TARGET:
        errors.append(f"current implementation target must be {CURRENT_TARGET}")
    simplified = decision_record.get("simplified_fallback")
    if not isinstance(simplified, dict):
        errors.append("simplified_fallback must be an object")
    else:
        if simplified.get("target_release") != "v1.5+":
            errors.append("simplified_fallback target_release must be v1.5+")
        if simplified.get("implementation_now") is not False:
            errors.append("simplified_fallback implementation_now must be false")
        if simplified.get("includes_compensation_transactions") is not False:
            errors.append("simplified_fallback must exclude compensation transactions")
        if simplified.get("includes_full_state_machine") is not False:
            errors.append("simplified_fallback must exclude full state machine")
    return errors


def validate_plan(plan: dict[str, Any], expected_summary: dict[str, Any]) -> list[str]:
    required = {
        "dataset_version",
        "story_key",
        "source_story",
        "upstream_stories",
        "artifact_paths",
        "runbook_path",
        "fixture_manifest",
        "required_blocking_signoff_roles",
        "owner_review_map",
        "decision_record",
        "claims",
    }
    errors = _validate_object_fields(
        plan, required=required, allowed=required, source="dryrun_plan"
    )
    if plan.get("dataset_version") != "saga_cross_epic_dryrun_v1":
        errors.append("dataset_version must be saga_cross_epic_dryrun_v1")
    if plan.get("story_key") != STORY_KEY:
        errors.append(f"story_key must be {STORY_KEY}")
    if plan.get("source_story") != "5.A.0c":
        errors.append("source_story must be 5.A.0c")
    if plan.get("upstream_stories") != UPSTREAM_STORIES:
        errors.append("upstream_stories must be 5.A.0a then 5.A.0b")

    artifact_paths = plan.get("artifact_paths")
    if not isinstance(artifact_paths, list):
        errors.append("artifact_paths must be a list")
    else:
        if artifact_paths[: len(EXPECTED_ARTIFACT_PATHS)] != EXPECTED_ARTIFACT_PATHS:
            errors.append("artifact_paths must start with the dry-run plan and sign-off example")
        for path_value in artifact_paths:
            errors.extend(_validate_artifact_path(path_value))
    errors.extend(_validate_runbook_path(plan.get("runbook_path")))
    errors.extend(_validate_fixture_manifest(plan.get("fixture_manifest"), expected_summary))
    errors.extend(_validate_owner_map(plan))
    errors.extend(_validate_decision(plan.get("decision_record")))
    errors.extend(_validate_claims(plan.get("claims")))
    errors.extend(validate_no_sensitive_values(plan, "dryrun_plan.json"))
    return errors


def validate_signoff_example(signoff: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    required = {
        "dataset_version",
        "example_only",
        "story_key",
        "status",
        "decision",
        "fixture_contract_version",
        "fixture_manifest_sha256",
        "review_duration_minutes",
        "meeting_started_at",
        "ci_status",
        "live_services_executed",
        "production_dryrun",
        "real_committee_approval",
        "required_roles",
        "consulted_roles",
        "open_risks",
    }
    errors = _validate_object_fields(
        signoff,
        required=required,
        allowed=required,
        source="owner_signoff.example.json",
    )
    if signoff.get("dataset_version") != "saga_owner_signoff_example_v1":
        errors.append("signoff dataset_version must be saga_owner_signoff_example_v1")
    if signoff.get("example_only") is not True:
        errors.append("example_only must be true")
    if signoff.get("story_key") != plan.get("story_key"):
        errors.append("story_key must match dryrun plan")
    if signoff.get("status") != "not_a_real_signoff":
        errors.append("status must be not_a_real_signoff")
    elif APPROVAL_WORD_PATTERN.search(str(signoff.get("status"))):
        errors.append("status must not use real approval language")
    if signoff.get("decision") != plan.get("decision_record", {}).get("decision"):
        errors.append("decision must match dryrun plan")
    if signoff.get("fixture_contract_version") != plan.get("fixture_manifest", {}).get("version"):
        errors.append("fixture_contract_version must match dryrun plan")
    if signoff.get("fixture_manifest_sha256") != plan.get("fixture_manifest", {}).get("sha256"):
        errors.append("fixture_manifest_sha256 must match dryrun plan")
    if signoff.get("review_duration_minutes") != 30:
        errors.append("review_duration_minutes must be 30")
    if signoff.get("meeting_started_at") != "placeholder-not-scheduled":
        errors.append("meeting_started_at must be placeholder-not-scheduled")
    if signoff.get("ci_status") != "not_run":
        errors.append("ci_status must be not_run")
    for key in ("live_services_executed", "production_dryrun", "real_committee_approval"):
        if signoff.get(key) is not False:
            errors.append(f"{key} must be false")
    if signoff.get("required_roles") != REQUIRED_BLOCKING_ROLES:
        errors.append("required_roles must be Billing Lead, Solver Lead, SRE")
    if signoff.get("consulted_roles") != CONSULTED_ROLES:
        errors.append("consulted_roles must be Provider Interface Lead")
    open_risks = signoff.get("open_risks")
    if (
        not isinstance(open_risks, list)
        or not open_risks
        or not all(isinstance(item, str) and item for item in open_risks)
    ):
        errors.append("open_risks must be a non-empty list of strings")
    errors.extend(validate_no_sensitive_values(signoff, "owner_signoff.example.json"))
    errors.extend(validate_no_fake_completion_claims(signoff, "owner_signoff.example.json"))
    return errors


def validate_all(
    plan_path: Path = PLAN_PATH,
    signoff_path: Path = SIGNOFF_PATH,
    runbook_path: Path = RUNBOOK_PATH,
) -> list[str]:
    errors: list[str] = []
    plan_data = load_json(plan_path)
    signoff_data = load_json(signoff_path)
    if not isinstance(plan_data, dict):
        return ["dryrun_plan.json must contain an object"]
    if not isinstance(signoff_data, dict):
        return ["owner_signoff.example.json must contain an object"]
    if not runbook_path.exists():
        errors.append("runbook path does not exist")
    else:
        errors.extend(validate_runbook_text(runbook_path.read_text(encoding="utf-8")))
    expected_summary = build_fixture_manifest_summary()
    errors.extend(validate_plan(plan_data, expected_summary))
    errors.extend(validate_signoff_example(signoff_data, plan_data))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--signoff", type=Path, default=SIGNOFF_PATH)
    parser.add_argument("--runbook", type=Path, default=RUNBOOK_PATH)
    args = parser.parse_args(argv)

    errors = validate_all(args.plan, args.signoff, args.runbook)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("saga cross-epic dry-run OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
