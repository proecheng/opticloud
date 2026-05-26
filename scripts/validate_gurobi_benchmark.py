from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools" / "gurobi_benchmark"
MANIFEST_PATH = TOOLS_DIR / "benchmark_manifest.json"
MANIFEST_SCHEMA_PATH = TOOLS_DIR / "benchmark_manifest.schema.json"
FIXTURE_SUITE_PATH = TOOLS_DIR / "lp_fixture_suite.json"
EVIDENCE_SCHEMA_PATH = TOOLS_DIR / "evidence_manifest.schema.json"
EVIDENCE_EXAMPLE_PATH = TOOLS_DIR / "evidence_manifest.example.json"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

ALLOWED_STATUSES = {
    "draft",
    "internal_ready",
    "evidence_required",
    "operator_run_required",
    "legal_review_required",
    "published",
}
ALLOWED_CLAIM_STATUSES = {
    "hypothesis",
    "methodology_ready",
    "operator_evidence_required",
    "gurobi_license_required",
    "verified",
}
ALLOWED_EVIDENCE_STATUSES = ALLOWED_CLAIM_STATUSES
ALLOWED_APPROVAL_STATUSES = {
    "operator_draft",
    "redaction_passed",
    "legal_review_required",
    "approved_for_publication",
}
REQUIRED_CATEGORIES = {
    "fixture_suite",
    "methodology",
    "whitepaper",
    "evidence_schema",
    "operator_runbook",
}
REQUIRED_ASSET_PATHS = {
    "tools/gurobi_benchmark/lp_fixture_suite.json",
    "tools/gurobi_benchmark/evidence_manifest.schema.json",
    "tools/gurobi_benchmark/evidence_manifest.example.json",
    "docs/benchmarks/gurobi-lp-benchmark-methodology.md",
    "docs/benchmarks/gurobi-lp-benchmark-whitepaper.md",
    "docs/runbooks/gurobi-lp-benchmark.md",
}
REQUIRED_FIXTURE_CATEGORIES = {
    "small_bounded",
    "resource_allocation",
    "blending",
    "transportation_style",
    "scheduling_style",
    "stress_scale_synthetic",
}
ALLOWED_SENSES = {"minimize", "maximize"}
ALLOWED_EXPECTED_STATUSES = {
    "optimal",
    "infeasible",
    "unbounded",
    "timeout_expected",
    "solver_error_expected",
}
FORBIDDEN_SUPERIORITY_CLAIMS = (
    "beats gurobi",
    "outperforms gurobi",
    "faster than gurobi",
    "cheaper than gurobi",
    "matches gurobi",
    "production-equivalent to gurobi",
    "verified benchmark results prove",
)
FORBIDDEN_ANALYTICS = ("gtag(", "googletagmanager", "segment.com", "mixpanel", "amplitude")
FORBIDDEN_SECRET_KEYS = {
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
    "license_key",
    "license_token",
    "grb_license_file",
    "hostname",
    "username",
    "email",
    "phone",
}
SECRET_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"license|host[_-]?name|user[_-]?name|email|phone|token)([_-]|$)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = {
    "bearer token": re.compile(r"bearer\s+[a-z0-9._~+/=-]{12,}", re.IGNORECASE),
    "credentialed url": re.compile(r"https?://[^/\s:@]+:[^/\s:@]+@"),
    "api key assignment": re.compile(
        r"(api[_-]?key|token|secret|license)\s*[:=]\s*[a-z0-9._~+/=-]{12,}",
        re.IGNORECASE,
    ),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b1[3-9]\d{9}\b"),
}
EVIDENCE_ROOT_REQUIRED = {
    "source_story",
    "example_only",
    "run_id",
    "fixture_suite_id",
    "environment_summary",
    "solver_versions",
    "run_policy",
    "aggregate_metrics",
    "per_fixture_results",
    "artifacts",
    "redaction_reviewed",
    "operator",
    "approval_status",
}
PER_FIXTURE_RESULT_REQUIRED = {
    "fixture_id",
    "opticloud_highs_status",
    "gurobi_status",
    "opticloud_runtime_seconds",
    "gurobi_runtime_seconds",
    "opticloud_objective",
    "gurobi_objective",
    "not_available_reason",
    "objective_delta",
    "primal_feasibility_residual",
    "notes",
}
PLACEHOLDER_STATUSES = {"not_run", "pending", "pending_verified_evidence"}
AGGREGATE_METRIC_REQUIRED = {
    "fixture_count",
    "comparable_count",
    "status_parity_count",
    "objective_tolerance_pass_count",
    "timeout_count",
    "error_count",
}
ARTIFACT_FIELDS = {"summary_table", "raw_result_manifest", "redaction_notes"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_path(path: Path) -> str:
    return path.as_posix()


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


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
                if normalized_key in FORBIDDEN_SECRET_KEYS or SECRET_KEY_PATTERN.search(str(key)):
                    errors.append(f"{source} contains forbidden secret-like key at {path}.{key}")
        if isinstance(value, str):
            lowered = value.lower()
            if "gurobi.lic" in lowered or "grb_license_file" in lowered:
                errors.append(f"{source} contains license file reference at {path}")
            for label, pattern in SECRET_VALUE_PATTERNS.items():
                if pattern.search(value):
                    errors.append(f"{source} contains forbidden {label} at {path}")
    return errors


def _validate_number(value: Any, label: str, *, nullable: bool = False) -> list[str]:
    if value is None and nullable:
        return []
    if isinstance(value, bool) or not isinstance(value, int | float):
        return [f"{label}: expected finite number"]
    if not math.isfinite(float(value)):
        return [f"{label}: non-finite numeric value"]
    return []


def _validate_number_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{label}: expected non-empty numeric list"]
    errors: list[str] = []
    for index, item in enumerate(value):
        errors.extend(_validate_number(item, f"{label}[{index}]"))
    return errors


def _has_unsupported_claim(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in FORBIDDEN_SUPERIORITY_CLAIMS)


def _has_external_analytics(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in FORBIDDEN_ANALYTICS)


def _has_live_marketing_url(text: str) -> bool:
    lowered = text.lower()
    return "https://opticloud.cn/benchmark" in lowered or "https://opticloud.cn/gurobi" in lowered


def validate_markdown_asset(
    root: Path,
    path: Path,
    required_fields: list[str],
) -> list[str]:
    errors: list[str] = []
    asset_path = root / path
    display_path = _repo_path(path)
    if not asset_path.exists():
        return [f"{display_path}: missing asset"]
    text = asset_path.read_text(encoding="utf-8")
    fields = _parse_frontmatter(text)
    for field in required_fields:
        if field not in fields:
            errors.append(f"{display_path}: missing frontmatter field {field}")
    status = fields.get("status")
    if status is not None and status not in ALLOWED_STATUSES:
        errors.append(f"{display_path}: invalid status {status}")
    claim_status = fields.get("claim_status")
    if claim_status is not None and claim_status not in ALLOWED_CLAIM_STATUSES:
        errors.append(f"{display_path}: invalid claim_status {claim_status}")
    evidence_status = fields.get("evidence_status")
    if evidence_status is not None and evidence_status not in ALLOWED_EVIDENCE_STATUSES:
        errors.append(f"{display_path}: invalid evidence_status {evidence_status}")
    if status == "published" and evidence_status != "verified":
        errors.append(f"{display_path}: published asset requires verified evidence")
    if _has_unsupported_claim(text):
        errors.append(f"{display_path}: unsupported benchmark superiority claim")
    if _has_external_analytics(text):
        errors.append(f"{display_path}: external analytics snippet")
    if _has_live_marketing_url(text):
        errors.append(f"{display_path}: live marketing URL")
    errors.extend(validate_no_sensitive_values(fields, display_path))
    return errors


def validate_fixture_suite(suite: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if suite.get("story_key") != "m4-5b-gurobi-benchmark-whitepaper":
        errors.append("fixture suite story_key must be m4-5b-gurobi-benchmark-whitepaper")
    if suite.get("fixture_count") != 30:
        errors.append("fixture suite fixture_count must be 30")
    fixtures = suite.get("fixtures")
    if not isinstance(fixtures, list):
        return errors + ["fixture suite fixtures must be a list"]
    expected_ids = [f"lp-{index:03d}" for index in range(1, 31)]
    fixture_ids = [fixture.get("id") for fixture in fixtures if isinstance(fixture, dict)]
    if fixture_ids != expected_ids:
        errors.append("fixture ids must be lp-001 through lp-030")
    if len(fixtures) != 30:
        errors.append("fixture suite must contain exactly 30 fixtures")

    categories: set[str] = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            errors.append("fixture entry must be an object")
            continue
        fixture_id = str(fixture.get("id", "<missing>"))
        required_fields = {
            "id",
            "category",
            "sense",
            "objective",
            "constraints",
            "bounds",
            "expected_status",
            "expected_highs",
            "source",
            "notes",
        }
        missing = required_fields - set(fixture)
        for field in sorted(missing):
            errors.append(f"{fixture_id}: missing fixture field {field}")
        category = fixture.get("category")
        if isinstance(category, str):
            categories.add(category)
        if fixture.get("sense") not in ALLOWED_SENSES:
            errors.append(f"{fixture_id}: invalid sense")
        if fixture.get("expected_status") not in ALLOWED_EXPECTED_STATUSES:
            errors.append(f"{fixture_id}: invalid expected_status")
        objective = fixture.get("objective")
        errors.extend(_validate_number_list(objective, f"{fixture_id}.objective"))
        width = len(objective) if isinstance(objective, list) else None

        constraints = fixture.get("constraints")
        if not isinstance(constraints, dict):
            errors.append(f"{fixture_id}: constraints must be an object")
            continue
        matrix = constraints.get("A")
        rhs = constraints.get("b")
        if not isinstance(matrix, list) or not matrix:
            errors.append(f"{fixture_id}.constraints.A: expected non-empty matrix")
        else:
            for row_index, row in enumerate(matrix):
                row_label = f"{fixture_id}.constraints.A[{row_index}]"
                errors.extend(_validate_number_list(row, row_label))
                if width is not None and isinstance(row, list) and len(row) != width:
                    errors.append(f"{row_label}: row width must equal objective length")
        errors.extend(_validate_number_list(rhs, f"{fixture_id}.constraints.b"))
        if isinstance(matrix, list) and isinstance(rhs, list) and len(rhs) != len(matrix):
            errors.append(f"{fixture_id}.constraints.b: length must equal row count")

        bounds = fixture.get("bounds")
        if not isinstance(bounds, dict):
            errors.append(f"{fixture_id}: bounds must be an object")
            continue
        lower = bounds.get("lower")
        upper = bounds.get("upper")
        errors.extend(_validate_number_list(lower, f"{fixture_id}.bounds.lower"))
        errors.extend(_validate_number_list(upper, f"{fixture_id}.bounds.upper"))
        if width is not None and isinstance(lower, list) and len(lower) != width:
            errors.append(f"{fixture_id}.bounds.lower: length must equal objective length")
        if width is not None and isinstance(upper, list) and len(upper) != width:
            errors.append(f"{fixture_id}.bounds.upper: length must equal objective length")
        if isinstance(lower, list) and isinstance(upper, list) and len(lower) == len(upper):
            for index, (lo, hi) in enumerate(zip(lower, upper, strict=True)):
                if isinstance(lo, int | float) and isinstance(hi, int | float) and lo > hi:
                    errors.append(f"{fixture_id}.bounds[{index}]: lower must be <= upper")

        expected_highs = fixture.get("expected_highs")
        if not isinstance(expected_highs, dict):
            errors.append(f"{fixture_id}: expected_highs must be an object")
        elif expected_highs.get("status") not in ALLOWED_EXPECTED_STATUSES:
            errors.append(f"{fixture_id}: invalid expected_highs.status")
        errors.extend(validate_no_sensitive_values(fixture, fixture_id))

    if not REQUIRED_FIXTURE_CATEGORIES.issubset(categories):
        errors.append("fixture suite missing required category coverage")
    return errors


def _validate_manifest(root: Path, suite: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not MANIFEST_PATH.exists():
        return ["tools/gurobi_benchmark/benchmark_manifest.json: missing manifest"]
    manifest = load_json(MANIFEST_PATH)
    if not MANIFEST_SCHEMA_PATH.exists():
        errors.append("tools/gurobi_benchmark/benchmark_manifest.schema.json: missing schema")
    else:
        schema = load_json(MANIFEST_SCHEMA_PATH)
        for field in ("story_key", "stage", "source_gap", "fixture_count", "assets"):
            if field not in set(schema.get("required", [])):
                errors.append(f"manifest schema: missing required field {field}")
    if manifest.get("story_key") != "m4-5b-gurobi-benchmark-whitepaper":
        errors.append("manifest: invalid story_key")
    if manifest.get("stage") != "M4.5":
        errors.append("manifest: stage must be M4.5")
    if manifest.get("source_gap") != "E3":
        errors.append("manifest: source_gap must be E3")
    if manifest.get("fixture_count") != 30 or manifest.get("fixture_count") != suite.get(
        "fixture_count"
    ):
        errors.append("manifest: fixture_count must match fixture suite")
    assets = manifest.get("assets", [])
    if not isinstance(assets, list) or not assets:
        return errors + ["manifest: assets must be a non-empty list"]
    paths = {asset.get("path") for asset in assets if isinstance(asset, dict)}
    if paths != REQUIRED_ASSET_PATHS:
        errors.append("manifest: asset path coverage drifted")
    categories = {asset.get("category") for asset in assets if isinstance(asset, dict)}
    if categories != REQUIRED_CATEGORIES:
        errors.append("manifest: categories drifted")
    for asset in assets:
        if not isinstance(asset, dict):
            errors.append("manifest: every asset must be an object")
            continue
        path_value = asset.get("path")
        if not isinstance(path_value, str):
            errors.append("manifest: asset path must be a string")
            continue
        if asset.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{path_value}: invalid manifest status")
        if asset.get("claim_status") not in ALLOWED_CLAIM_STATUSES:
            errors.append(f"{path_value}: invalid manifest claim_status")
        if asset.get("evidence_status") not in ALLOWED_EVIDENCE_STATUSES:
            errors.append(f"{path_value}: invalid manifest evidence_status")
        if not asset.get("source_refs"):
            errors.append(f"{path_value}: missing source_refs")
        if not asset.get("required_fields"):
            errors.append(f"{path_value}: missing required_fields")
        full_path = root / path_value
        if not full_path.exists():
            errors.append(f"{path_value}: missing asset")
        if path_value.endswith(".md"):
            errors.extend(
                validate_markdown_asset(
                    root,
                    Path(path_value),
                    list(asset.get("required_fields", [])),
                )
            )
    return errors


def _artifact_path_errors(artifacts: dict[str, Any], run_id: str) -> list[str]:
    errors: list[str] = []
    expected_prefix = f"reports/gurobi-benchmark/{run_id}/"
    for key in ARTIFACT_FIELDS:
        value = artifacts.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"artifacts.{key}: missing artifact path")
            continue
        lowered = value.lower()
        if "://" in lowered:
            errors.append(f"artifacts.{key}: artifact path must not be a URL")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            errors.append(f"artifacts.{key}: artifact path must not traverse")
        if not value.startswith(expected_prefix):
            errors.append(f"artifacts.{key}: artifact path must stay under run directory")
    return errors


def _derived_aggregate(results: list[dict[str, Any]]) -> dict[str, int]:
    comparable = [
        result
        for result in results
        if result.get("opticloud_objective") is not None
        and result.get("gurobi_objective") is not None
    ]
    return {
        "fixture_count": len(results),
        "comparable_count": len(comparable),
        "status_parity_count": sum(
            1
            for result in results
            if result.get("opticloud_highs_status") == result.get("gurobi_status")
        ),
        "objective_tolerance_pass_count": sum(
            1
            for result in comparable
            if isinstance(result.get("objective_delta"), int | float)
            and abs(float(result["objective_delta"])) <= 1e-7
        ),
        "timeout_count": sum(
            1
            for result in results
            if "timeout" in str(result.get("opticloud_highs_status", "")).lower()
            or "timeout" in str(result.get("gurobi_status", "")).lower()
        ),
        "error_count": sum(
            1
            for result in results
            if "error" in str(result.get("opticloud_highs_status", "")).lower()
            or "error" in str(result.get("gurobi_status", "")).lower()
        ),
    }


def validate_evidence_manifest(
    evidence: dict[str, Any],
    suite: dict[str, Any],
    *,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    for field in sorted(EVIDENCE_ROOT_REQUIRED - set(evidence)):
        errors.append(f"evidence: missing root field {field}")
    if errors:
        return errors
    if evidence.get("source_story") != "m4-5b-gurobi-benchmark-whitepaper":
        errors.append("evidence source_story must be m4-5b-gurobi-benchmark-whitepaper")
    if evidence.get("fixture_suite_id") != suite.get("suite_id"):
        errors.append("evidence fixture_suite_id must match fixture suite")
    if real_evidence and evidence.get("example_only") is not False:
        errors.append("real evidence must set example_only=false")
    if real_evidence and evidence.get("redaction_reviewed") is not True:
        errors.append("real evidence must set redaction_reviewed=true")
    if evidence.get("approval_status") not in ALLOWED_APPROVAL_STATUSES:
        errors.append("evidence approval_status is invalid")
    results = evidence.get("per_fixture_results")
    if not isinstance(results, list):
        return errors + ["evidence per_fixture_results must be a list"]
    expected_ids = [fixture["id"] for fixture in suite.get("fixtures", [])]
    result_ids = [result.get("fixture_id") for result in results if isinstance(result, dict)]
    if result_ids != expected_ids:
        errors.append("evidence fixture ids must match suite fixture ids")
    if len(results) != 30:
        errors.append("evidence must include exactly 30 per-fixture results")
    for result in results:
        if not isinstance(result, dict):
            errors.append("evidence per-fixture result must be an object")
            continue
        fixture_id = str(result.get("fixture_id", "<missing>"))
        for field in sorted(PER_FIXTURE_RESULT_REQUIRED - set(result)):
            errors.append(f"{fixture_id}: missing result field {field}")
        for field in (
            "opticloud_runtime_seconds",
            "gurobi_runtime_seconds",
            "opticloud_objective",
            "gurobi_objective",
            "objective_delta",
            "primal_feasibility_residual",
        ):
            errors.extend(
                _validate_number(result.get(field), f"{fixture_id}.{field}", nullable=True)
            )
        if real_evidence:
            for status_field in ("opticloud_highs_status", "gurobi_status"):
                status_value = str(result.get(status_field, "")).lower()
                if status_value in PLACEHOLDER_STATUSES:
                    errors.append(
                        f"{fixture_id}.{status_field}: real evidence must not use placeholder status"
                    )
            for runtime_field in ("opticloud_runtime_seconds", "gurobi_runtime_seconds"):
                if result.get(runtime_field) is None:
                    errors.append(f"{fixture_id}.{runtime_field}: real evidence requires runtime")

    aggregate = evidence.get("aggregate_metrics")
    if not isinstance(aggregate, dict):
        errors.append("evidence aggregate_metrics must be an object")
    else:
        for field in sorted(AGGREGATE_METRIC_REQUIRED - set(aggregate)):
            errors.append(f"aggregate_metrics: missing {field}")
        derived = _derived_aggregate([result for result in results if isinstance(result, dict)])
        for field, expected_value in derived.items():
            if aggregate.get(field) != expected_value:
                errors.append(f"aggregate {field} must equal {expected_value}")

    artifacts = evidence.get("artifacts")
    run_id = evidence.get("run_id")
    if isinstance(artifacts, dict) and isinstance(run_id, str):
        errors.extend(_artifact_path_errors(artifacts, run_id))
    else:
        errors.append("evidence artifacts and run_id are required for artifact validation")
    errors.extend(validate_no_sensitive_values(evidence, "evidence"))
    return errors


def _validate_docs(root: Path) -> list[str]:
    errors: list[str] = []
    methodology = root / "docs/benchmarks/gurobi-lp-benchmark-methodology.md"
    runbook = root / "docs/runbooks/gurobi-lp-benchmark.md"
    whitepaper = root / "docs/benchmarks/gurobi-lp-benchmark-whitepaper.md"
    required_methodology_terms = (
        "Solver identities",
        "BYO Gurobi license boundary",
        "Metric definitions",
        "Publication gate",
    )
    if methodology.exists():
        text = methodology.read_text(encoding="utf-8")
        for term in required_methodology_terms:
            if term not in text:
                errors.append(f"methodology: missing {term}")
    if runbook.exists():
        text = runbook.read_text(encoding="utf-8")
        for term in ("reports/gurobi-benchmark/<run_id>/", "Do not commit", "redaction"):
            if term not in text:
                errors.append(f"runbook: missing {term}")
    if whitepaper.exists():
        fields = _parse_frontmatter(whitepaper.read_text(encoding="utf-8"))
        if fields.get("status") != "evidence_required":
            errors.append("whitepaper: status must remain evidence_required")
        if fields.get("evidence_status") != "operator_evidence_required":
            errors.append("whitepaper: evidence_status must be operator_evidence_required")
    return errors


def _validate_ci(root: Path) -> list[str]:
    errors: list[str] = []
    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    expected = (
        "gurobi_benchmark:",
        "docs/benchmarks/**",
        "docs/runbooks/gurobi-lp-benchmark.md",
        "tools/gurobi_benchmark/**",
        "scripts/validate_gurobi_benchmark.py",
        "tests/test_gurobi_benchmark.py",
        "reports/gurobi-benchmark/**",
        "gurobi-benchmark-validation",
        "uv run python scripts/validate_gurobi_benchmark.py",
        "uv run pytest tests/test_gurobi_benchmark.py",
    )
    for item in expected:
        if item not in ci:
            errors.append(f"ci: missing {item}")
    return errors


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    root = root.resolve()
    if not FIXTURE_SUITE_PATH.exists():
        return ["tools/gurobi_benchmark/lp_fixture_suite.json: missing fixture suite"]
    suite = load_json(FIXTURE_SUITE_PATH)
    if not isinstance(suite, dict):
        return ["fixture suite must be a JSON object"]
    errors.extend(validate_fixture_suite(suite))
    errors.extend(_validate_manifest(root, suite))
    if EVIDENCE_SCHEMA_PATH.exists():
        schema = load_json(EVIDENCE_SCHEMA_PATH)
        if set(schema.get("required", [])) != EVIDENCE_ROOT_REQUIRED:
            errors.append("evidence schema root required fields drifted")
    else:
        errors.append("tools/gurobi_benchmark/evidence_manifest.schema.json: missing schema")
    if EVIDENCE_EXAMPLE_PATH.exists():
        example = load_json(EVIDENCE_EXAMPLE_PATH)
        if isinstance(example, dict):
            errors.extend(validate_evidence_manifest(example, suite, real_evidence=False))
        else:
            errors.append("evidence example must be a JSON object")
    else:
        errors.append("tools/gurobi_benchmark/evidence_manifest.example.json: missing example")
    errors.extend(_validate_docs(root))
    errors.extend(_validate_ci(root))

    reports_root = root / "reports" / "gurobi-benchmark"
    if reports_root.exists():
        for evidence_path in reports_root.glob("*/evidence_manifest.json"):
            evidence = load_json(evidence_path)
            if isinstance(evidence, dict):
                errors.extend(validate_evidence_manifest(evidence, suite, real_evidence=True))
            else:
                errors.append(
                    f"{_repo_path(evidence_path.relative_to(root))}: evidence must be object"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate M4.5b Gurobi benchmark package.")
    parser.add_argument("--evidence", type=Path, help="Validate a real evidence manifest.")
    args = parser.parse_args()

    if not FIXTURE_SUITE_PATH.exists():
        errors = ["tools/gurobi_benchmark/lp_fixture_suite.json: missing fixture suite"]
    else:
        suite = load_json(FIXTURE_SUITE_PATH)
        if not isinstance(suite, dict):
            errors = ["fixture suite must be a JSON object"]
        elif args.evidence:
            evidence = load_json(args.evidence)
            if not isinstance(evidence, dict):
                errors = [f"{args.evidence}: evidence must be a JSON object"]
            else:
                errors = validate_evidence_manifest(evidence, suite, real_evidence=True)
        else:
            errors = validate_repository(REPO_ROOT)

    if errors:
        for error in errors:
            sys.stderr.write(f"ERROR: {error}\n")
        return 1
    if args.evidence:
        sys.stdout.write("gurobi benchmark evidence OK\n")
    else:
        sys.stdout.write("gurobi benchmark package OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
