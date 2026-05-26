"""Validate M3.9 image archival pipeline contract assets.

The default path is static: it validates committed plan and example evidence
without cloud, Docker, signing, SBOM, Vault, registry, or network operations.
Real operator evidence can be validated explicitly with --evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVAL_DIR = REPO_ROOT / "infra" / "image-archival"
TOOLS_DIR = REPO_ROOT / "tools" / "image_archival"
ARCHIVE_PLAN_PATH = ARCHIVAL_DIR / "archive-plan.json"
PIPELINE_PLAN_PATH = ARCHIVAL_DIR / "pipeline-plan.json"
PIPELINE_SCHEMA_PATH = ARCHIVAL_DIR / "pipeline-plan.schema.json"
EVIDENCE_SCHEMA_PATH = TOOLS_DIR / "evidence_manifest.schema.json"
EVIDENCE_EXAMPLE_PATH = TOOLS_DIR / "evidence_manifest.example.json"

EXPECTED_CLOCK = {"source": "reproduction_vouchers.created_at", "timezone": "UTC"}
EXPECTED_TIERS = (
    ("hot_acr_ee", 0, 90),
    ("warm_s3_standard_ia", 91, 365),
    ("cold_s3_glacier", 366, 1826),
)
EXPECTED_STAGES = (
    "provider_image_push",
    "cosign_sign_and_index",
    "hot_acr_ee_retention",
    "warm_s3_standard_ia_transition",
    "cold_s3_glacier_transition",
    "vault_kms_backup",
    "quarterly_restore_drill",
)
REQUIRED_IMAGE_FIELDS = {
    "image_digest",
    "cosign_signature_ref",
    "sbom_ref",
    "source_commit_sha",
    "build_timestamp_utc",
    "provider_id",
    "solver",
    "model_version",
    "repository_ref",
}
REQUIRED_ARCHIVE_INDEX_FIELDS = {
    "voucher_id",
    "voucher_created_at_utc",
    "provider_id",
    "solver",
    "model_version",
    "image_digest",
    "cosign_signature_ref",
    "sbom_ref",
    "storage_tier",
    "registry_or_object_ref",
    "kms_key_backup_ref",
    "transition_due_utc",
    "transition_observed_utc",
    "artifact_checksum",
    "cosign_verified",
    "sbom_verified",
}
REQUIRED_KMS_METADATA = {
    "kms_key_id",
    "kms_key_backup_ref",
    "backup_created_at_utc",
    "backup_checksum",
    "restore_tested_at_utc",
    "restore_test_result",
}
EVIDENCE_ROOT_REQUIRED = {
    "source_story",
    "example_only",
    "run_id",
    "commit_sha",
    "archive_plan_sha256",
    "pipeline_plan_sha256",
    "environment",
    "started_utc",
    "ended_utc",
    "tier_results",
    "kms_backup_results",
    "artifacts",
    "redaction_reviewed",
    "operator",
}
TIER_RESULT_REQUIRED = {
    "voucher_id",
    "voucher_created_at_utc",
    "storage_tier",
    "image_digest",
    "registry_or_object_ref",
    "artifact_checksum",
    "cosign_verified",
    "sbom_verified",
    "kms_backup_ref",
    "kms_backup_verified",
    "restore_status",
    "restore_target_minutes",
    "restore_requested_utc",
    "restore_completed_utc",
    "outcome",
}
KMS_RESULT_REQUIRED = {
    "kms_key_id",
    "kms_key_backup_ref",
    "backup_created_at_utc",
    "backup_checksum",
    "restore_tested_at_utc",
    "restore_test_result",
}
ARTIFACT_FIELDS = {"restore_report", "redaction_audit", "drill_log"}
FORBIDDEN_PASS_CLAIMS = {
    "cold_restore_5m_pass",
    "g7_cloud_pipeline_live",
    "acr_ee_provisioned",
    "glacier_restore_slo_pass",
}
SECRET_KEY_EXACT = {
    "authorization",
    "token",
    "auth_token",
    "bearer_token",
    "api_token",
    "access_token",
    "refresh_token",
    "session_token",
    "cookie",
    "password",
    "secret",
    "api_key",
    "private_key",
    "access_key",
    "user_id",
    "email",
    "phone",
    "prompt",
}
SECRET_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"user[_-]?id|cookie|phone|email|prompt|token)([_-]|$)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = {
    "bearer token": re.compile(r"bearer\s+[a-z0-9._~+/=-]{12,}", re.IGNORECASE),
    "credentialed url": re.compile(r"https?://[^/\s:@]+:[^/\s:@]+@"),
    "api key assignment": re.compile(
        r"(api[_-]?key|token|secret)\s*[:=]\s*[a-z0-9._~+/=-]{12,}", re.IGNORECASE
    ),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
                if normalized_key in SECRET_KEY_EXACT or SECRET_KEY_PATTERN.search(str(key)):
                    errors.append(f"{source} contains forbidden secret-like key at {path}.{key}")
        if isinstance(value, str):
            if path.endswith(".$schema") or path.endswith(".$id"):
                continue
            for label, pattern in SECRET_VALUE_PATTERNS.items():
                if pattern.search(value):
                    errors.append(f"{source} contains forbidden {label} at {path}")
    return errors


def _missing_errors(actual: object, expected: set[str], label: str) -> list[str]:
    if not isinstance(actual, list):
        return [f"{label} missing: {field}" for field in sorted(expected)]
    return [f"{label} missing: {field}" for field in sorted(expected - set(actual))]


def _validate_schema_sets(
    pipeline_schema: dict[str, Any], evidence_schema: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    evidence_root_required = set(evidence_schema["required"])
    artifact_required = set(evidence_schema["properties"]["artifacts"]["required"])
    image_fields = set(pipeline_schema["properties"]["required_image_fields"]["items"]["enum"])
    archive_fields = set(
        pipeline_schema["properties"]["archive_index_required_fields"]["items"]["enum"]
    )
    kms_fields = set(
        pipeline_schema["properties"]["kms_backup_requirements"]["properties"]["minimum_metadata"][
            "items"
        ]["enum"]
    )
    tier_required = set(evidence_schema["properties"]["tier_results"]["items"]["required"])
    if image_fields != REQUIRED_IMAGE_FIELDS:
        errors.append("pipeline schema required_image_fields drifted")
    if archive_fields != REQUIRED_ARCHIVE_INDEX_FIELDS:
        errors.append("pipeline schema archive_index_required_fields drifted")
    if kms_fields != REQUIRED_KMS_METADATA:
        errors.append("pipeline schema kms minimum_metadata drifted")
    if tier_required != TIER_RESULT_REQUIRED:
        errors.append("evidence schema tier result required fields drifted")
    if evidence_root_required != EVIDENCE_ROOT_REQUIRED:
        errors.append("evidence schema root required fields drifted")
    if artifact_required != ARTIFACT_FIELDS:
        errors.append("evidence schema artifact required fields drifted")
    return errors


def validate_pipeline_plan(plan: dict[str, Any], archive_plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("plan_version") != "image_archival_pipeline_v1":
        errors.append("plan_version must be image_archival_pipeline_v1")
    if plan.get("source_story") != "M3.9":
        errors.append("source_story must be M3.9")
    if plan.get("source_gap") != "G7":
        errors.append("source_gap must be G7")
    if plan.get("archive_plan_sha256") != canonical_sha256(archive_plan):
        errors.append("archive_plan_sha256 does not match archive-plan.json")
    if plan.get("evidence_directory") != "reports/image-archival":
        errors.append("evidence_directory must be reports/image-archival")

    clock = plan.get("clock")
    if not isinstance(clock, dict):
        errors.append("clock must be an object")
    else:
        if clock.get("source") != EXPECTED_CLOCK["source"]:
            errors.append("clock.source must be reproduction_vouchers.created_at")
        if clock.get("timezone") != EXPECTED_CLOCK["timezone"]:
            errors.append("clock.timezone must be UTC")

    tiers = plan.get("tiers")
    if not isinstance(tiers, list):
        errors.append("tiers must be a list")
    elif len(tiers) != len(EXPECTED_TIERS):
        errors.append("tiers must contain exactly three entries")
    else:
        for index, (expected_name, expected_start, expected_end) in enumerate(EXPECTED_TIERS):
            tier = tiers[index]
            if not isinstance(tier, dict):
                errors.append(f"tier {index} must be an object")
                continue
            if tier.get("name") != expected_name:
                errors.append(f"tier {index} name must be {expected_name}")
            if tier.get("day_start") != expected_start or tier.get("day_end") != expected_end:
                errors.append(f"{expected_name} must cover days {expected_start}-{expected_end}")

    stage_ids = [
        stage.get("stage_id") for stage in plan.get("stages", []) if isinstance(stage, dict)
    ]
    if stage_ids != list(EXPECTED_STAGES):
        errors.append("stage order must be " + ", ".join(EXPECTED_STAGES))

    transition_policy = plan.get("transition_policy")
    if not isinstance(transition_policy, dict):
        errors.append("transition_policy must be an object")
    else:
        if transition_policy.get("voucher_clock_required") is not True:
            errors.append("voucher_clock_required must be true")
        if transition_policy.get("allows_object_age_only_lifecycle") is not False:
            errors.append("object-age-only lifecycle is forbidden")
        errors.extend(
            _missing_errors(
                transition_policy.get("required_fields"),
                {"voucher_created_at_utc", "transition_due_utc", "transition_observed_utc"},
                "transition_policy.required_fields",
            )
        )

    identity_policy = plan.get("identity_policy")
    if not isinstance(identity_policy, dict):
        errors.append("identity_policy must be an object")
    else:
        if identity_policy.get("digest_required") is not True:
            errors.append("digest_required must be true")
        if identity_policy.get("allows_tag_only_reference") is not False:
            errors.append("tag-only references are forbidden")

    errors.extend(
        _missing_errors(
            plan.get("required_image_fields"), REQUIRED_IMAGE_FIELDS, "required_image_fields"
        )
    )
    errors.extend(
        _missing_errors(
            plan.get("archive_index_required_fields"),
            REQUIRED_ARCHIVE_INDEX_FIELDS,
            "archive_index_required_fields",
        )
    )

    kms = plan.get("kms_backup_requirements")
    if not isinstance(kms, dict):
        errors.append("kms_backup_requirements must be an object")
    else:
        if kms.get("required") is not True:
            errors.append("kms_backup_requirements.required must be true")
        if kms.get("reference_field") != "kms_key_backup_ref":
            errors.append("kms_backup_requirements.reference_field must be kms_key_backup_ref")
        errors.extend(
            _missing_errors(
                kms.get("minimum_metadata"),
                REQUIRED_KMS_METADATA,
                "kms_backup_requirements.minimum_metadata",
            )
        )
        if kms.get("payload_policy") != "do_not_commit_backup_payloads_or_tokens":
            errors.append("kms backup payload policy must forbid committed payloads or tokens")

    restore_targets = plan.get("restore_targets")
    if not isinstance(restore_targets, dict):
        errors.append("restore_targets must be an object")
    else:
        cold = restore_targets.get("cold_s3_glacier")
        if not isinstance(cold, dict):
            errors.append("cold_s3_glacier restore target must be an object")
        else:
            if cold.get("target_minutes") != 1440:
                errors.append("cold_s3_glacier target_minutes must be 1440")
            if cold.get("allows_five_minute_claim") is not False:
                errors.append("cold_s3_glacier must not allow five-minute claims")

    errors.extend(validate_no_sensitive_values(plan, "pipeline-plan.json"))
    return errors


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _artifact_path_errors(path_value: str, run_id: str, source: str) -> list[str]:
    errors: list[str] = []
    if "://" in path_value:
        errors.append(f"{source} artifact path must not be a URL: {path_value}")
    if path_value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", path_value):
        errors.append(f"{source} artifact path must be repository-relative: {path_value}")
    if ".." in Path(path_value).parts:
        errors.append(f"{source} artifact path must not traverse: {path_value}")
    required_prefix = f"reports/image-archival/{run_id}/"
    if not path_value.startswith(required_prefix):
        errors.append(f"{source} artifact path must stay under {required_prefix}: {path_value}")
    return errors


def validate_evidence_manifest(
    evidence: dict[str, Any],
    plan: dict[str, Any],
    archive_plan: dict[str, Any],
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    if set(evidence) - (EVIDENCE_ROOT_REQUIRED | FORBIDDEN_PASS_CLAIMS):
        for key in sorted(set(evidence) - (EVIDENCE_ROOT_REQUIRED | FORBIDDEN_PASS_CLAIMS)):
            errors.append(f"{source} unexpected field {key}")
    for key in sorted(EVIDENCE_ROOT_REQUIRED - set(evidence)):
        errors.append(f"{source} missing required field {key}")
    run_id = evidence.get("run_id")
    if not isinstance(run_id, str):
        return errors + [f"{source} run_id must be a string"]
    if evidence.get("source_story") != "M3.9":
        errors.append(f"{source} source_story must be M3.9")
    if real_evidence and evidence.get("example_only") is not False:
        errors.append(f"{source} real evidence must set example_only=false")
    if not real_evidence and evidence.get("example_only") is not True:
        errors.append(f"{source} example evidence must set example_only=true")
    if evidence.get("archive_plan_sha256") != canonical_sha256(archive_plan):
        errors.append(f"{source} archive_plan_sha256 does not match archive-plan.json")
    if evidence.get("pipeline_plan_sha256") != canonical_sha256(plan):
        errors.append(f"{source} pipeline_plan_sha256 does not match pipeline-plan.json")

    started = _parse_utc_timestamp(evidence.get("started_utc"))
    ended = _parse_utc_timestamp(evidence.get("ended_utc"))
    if started is None or ended is None:
        errors.append(f"{source} started_utc and ended_utc must be valid UTC timestamps")
    elif ended <= started:
        errors.append(f"{source} ended_utc must be after started_utc")

    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append(f"{source} artifacts must be an object")
    else:
        if set(artifacts) != ARTIFACT_FIELDS:
            errors.append(f"{source} artifact fields drifted")
        for key in sorted(ARTIFACT_FIELDS & set(artifacts)):
            value = artifacts.get(key)
            if isinstance(value, str):
                errors.extend(_artifact_path_errors(value, run_id, f"{source} {key}"))
            else:
                errors.append(f"{source} {key} must be a string")

    tier_results = evidence.get("tier_results")
    if not isinstance(tier_results, list):
        return errors + [f"{source} tier_results must be a list"]
    tier_names: list[str] = []
    for result in tier_results:
        if not isinstance(result, dict):
            errors.append(f"{source} tier result must be an object")
            continue
        for key in sorted(TIER_RESULT_REQUIRED - set(result)):
            errors.append(f"{source} tier result missing required field {key}")
        tier = result.get("storage_tier")
        if isinstance(tier, str):
            tier_names.append(tier)
        if (
            result.get("storage_tier") == "cold_s3_glacier"
            and result.get("restore_target_minutes") != 1440
        ):
            errors.append(f"{source} cold_s3_glacier restore_target_minutes must be 1440")
        for key in ("cosign_verified", "sbom_verified", "kms_backup_verified"):
            if result.get(key) is not True:
                errors.append(f"{source} {key} must be true")
    expected_tiers = {tier[0] for tier in EXPECTED_TIERS}
    if set(tier_names) != expected_tiers:
        errors.append(f"{source} real evidence must include all storage tiers")

    kms_results = evidence.get("kms_backup_results")
    if not isinstance(kms_results, list) or not kms_results:
        errors.append(f"{source} kms_backup_results must be a non-empty list")
    elif isinstance(kms_results, list):
        for result in kms_results:
            if not isinstance(result, dict):
                errors.append(f"{source} kms result must be an object")
                continue
            for key in sorted(KMS_RESULT_REQUIRED - set(result)):
                errors.append(f"{source} kms result missing required field {key}")
            if result.get("restore_test_result") != "passed":
                errors.append(f"{source} kms restore_test_result must be passed")

    for path, value in _walk_values(evidence):
        for claim in FORBIDDEN_PASS_CLAIMS:
            if path.endswith(f".{claim}") and value:
                errors.append(f"{source} cannot claim {claim}")
    errors.extend(validate_no_sensitive_values(evidence, source))
    return errors


def validate_evidence_path_mode(path: Path) -> list[str]:
    relative = path.as_posix()
    if path.is_absolute():
        try:
            relative = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        except ValueError:
            return ["image archival evidence path must be inside the repository"]
    if not relative.startswith("reports/image-archival/") or not relative.endswith(
        "/evidence_manifest.json"
    ):
        return [
            "image archival evidence path must be "
            "reports/image-archival/<run_id>/evidence_manifest.json"
        ]
    return []


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    archive_plan = load_json(ARCHIVE_PLAN_PATH)
    pipeline_plan = load_json(PIPELINE_PLAN_PATH)
    pipeline_schema = load_json(PIPELINE_SCHEMA_PATH)
    evidence_schema = load_json(EVIDENCE_SCHEMA_PATH)
    evidence_example = load_json(EVIDENCE_EXAMPLE_PATH)
    if not isinstance(archive_plan, dict):
        return ["archive-plan.json must contain an object"]
    if not isinstance(pipeline_plan, dict):
        return ["pipeline-plan.json must contain an object"]
    errors.extend(validate_pipeline_plan(pipeline_plan, archive_plan))
    if isinstance(pipeline_schema, dict) and isinstance(evidence_schema, dict):
        errors.extend(_validate_schema_sets(pipeline_schema, evidence_schema))
    else:
        errors.append("schemas must contain objects")
    if isinstance(evidence_example, dict):
        errors.extend(
            validate_evidence_manifest(
                evidence_example,
                pipeline_plan,
                archive_plan,
                source="evidence_manifest.example.json",
                real_evidence=False,
            )
        )
    else:
        errors.append("evidence_manifest.example.json must contain an object")
    if evidence_path is not None:
        errors.extend(validate_evidence_path_mode(evidence_path))
        evidence = load_json(evidence_path)
        if isinstance(evidence, dict):
            errors.extend(
                validate_evidence_manifest(
                    evidence,
                    pipeline_plan,
                    archive_plan,
                    source=evidence_path.as_posix(),
                    real_evidence=True,
                )
            )
        else:
            errors.append(f"{evidence_path} must contain an object")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Optional real evidence under reports/image-archival/<run_id>/",
    )
    args = parser.parse_args(argv)
    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("image archival pipeline OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
