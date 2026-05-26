"""Validate M3.6d API gateway performance baseline assets.

The validator is static by default. It validates real operator evidence only
when an explicit manifest is passed with --evidence.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PERF_DIR = REPO_ROOT / "tools" / "api_gateway_perf"
PLAN_PATH = PERF_DIR / "perf_baseline_plan.json"
SCHEMA_PATH = PERF_DIR / "evidence_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = PERF_DIR / "evidence_manifest.example.json"
LOCUSTFILE_PATH = PERF_DIR / "locustfile.py"

ENDPOINT_CLASSES = ("algorithms_public", "auth_api_keys", "business_demo")
ARTIFACT_FIELDS = {
    "locust_report",
    "grafana_dashboard",
    "prometheus_snapshot",
    "latency_summary",
}
ENDPOINT_REQUIRED_FIELDS = {
    "endpoint_class",
    "method",
    "path",
    "auth_mode",
    "request_count",
    "success_count",
    "http_error_rate",
    "locust_p50_ms",
    "locust_p95_ms",
    "locust_p99_ms",
    "prometheus_histogram_quantile_p95_ms",
    "threshold_p95_ms",
}
ROOT_REQUIRED_FIELDS = {
    "source_story",
    "run_id",
    "example_only",
    "generated_by",
    "commit_sha",
    "environment",
    "plan_sha256",
    "profile",
    "started_utc",
    "ended_utc",
    "duration_seconds",
    "endpoint_results",
    "artifacts",
}
EXPECTED_ENDPOINTS: dict[str, dict[str, Any]] = {
    "algorithms_public": {
        "method": "GET",
        "path": "/v1/algorithms",
        "auth_mode": "none",
        "p95_threshold_ms": 200,
    },
    "auth_api_keys": {
        "method": "GET",
        "path": "/v1/auth/api_keys",
        "auth_mode": "jwt_bearer_env",
        "auth_env_var": "API_GATEWAY_PERF_JWT",
        "p95_threshold_ms": 200,
    },
    "business_demo": {
        "method": "POST",
        "path": "/v1/optimizations/demo",
        "auth_mode": "none",
        "p95_threshold_ms": 500,
    },
}
FORBIDDEN_PASS_CLAIMS = {
    "chat_load_pass",
    "incident_fallback_pass",
    "hard_gate_pass",
    "staging_pass",
}
SECRET_KEY_EXACT = {
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
}
SECRET_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer)([_-]|$)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = {
    "bearer token": re.compile(r"bearer\s+[a-z0-9._~+/=-]{12,}", re.IGNORECASE),
    "api key assignment": re.compile(
        r"(api[_-]?key|token|secret)\s*[:=]\s*[a-z0-9._~+/=-]{12,}", re.IGNORECASE
    ),
    "generic sk key": re.compile(r"\bsk-[a-zA-Z0-9]{16,}\b"),
    "credentialed url": re.compile(r"https?://[^/\s:@]+:[^/\s:@]+@"),
    "windows absolute path": re.compile(r"^[A-Za-z]:[\\/]"),
}


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


def _walk_values(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    values = [(path, value)]
    if isinstance(value, dict):
        for key, nested in value.items():
            values.extend(_walk_values(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            values.extend(_walk_values(nested, f"{path}[{index}]"))
    return values


def validate_no_secret_like_values(data: Any, source: str) -> list[str]:
    errors: list[str] = []
    for path, value in _walk_values(data):
        if isinstance(value, dict):
            for key in value:
                normalized_key = str(key).lower().replace("-", "_")
                if normalized_key in SECRET_KEY_EXACT or SECRET_KEY_PATTERN.search(str(key)):
                    errors.append(f"{source} contains forbidden secret-like key at {path}.{key}")
        if isinstance(value, str):
            for label, pattern in SECRET_VALUE_PATTERNS.items():
                if pattern.search(value):
                    errors.append(f"{source} contains forbidden {label} at {path}")
            if value.startswith(("http://", "https://")) and "opticloud.cn" in value:
                errors.append(f"{source} contains forbidden production hostname at {path}")
    return errors


def _require_numeric(data: dict[str, Any], key: str, errors: list[str], source: str) -> None:
    if not isinstance(data.get(key), int | float):
        errors.append(f"{source} {key} must be numeric")


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_values: dict[str, Any] = {
        "dataset_version": "api_gateway_perf_baseline_v1",
        "source_story": "M3.6d",
        "evidence_directory": "reports/api-gateway-perf",
        "grafana_dashboard_required": True,
        "prometheus_histogram_quantile": 0.95,
        "threshold_operator": "strict_less_than",
    }
    for key, expected in expected_values.items():
        if plan.get(key) != expected:
            errors.append(f"perf_baseline_plan.json {key} must be {expected}")

    profile = plan.get("profile")
    if not isinstance(profile, dict):
        errors.append("perf_baseline_plan.json profile must be an object")
    else:
        expected_profile: dict[str, Any] = {
            "name": "gateway_baseline",
            "users": 100,
            "spawn_rate_per_second": 10,
            "run_time_seconds": 1800,
        }
        for key, expected in expected_profile.items():
            if profile.get(key) != expected:
                errors.append(f"gateway_baseline {key} must be {expected}")

    endpoints = plan.get("endpoints")
    if not isinstance(endpoints, list):
        return errors + ["perf_baseline_plan.json endpoints must be a list"]
    if [endpoint.get("endpoint_class") for endpoint in endpoints if isinstance(endpoint, dict)] != [
        *ENDPOINT_CLASSES
    ]:
        errors.append("perf_baseline_plan.json endpoint classes must be in canonical order")

    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            errors.append("perf_baseline_plan.json endpoint must be an object")
            continue
        endpoint_class = endpoint.get("endpoint_class")
        if endpoint_class not in EXPECTED_ENDPOINTS:
            errors.append(f"unexpected endpoint_class {endpoint_class}")
            continue
        expected_endpoint = EXPECTED_ENDPOINTS[str(endpoint_class)]
        for key, expected in expected_endpoint.items():
            if endpoint.get(key) != expected:
                errors.append(f"{endpoint_class} {key} must be {expected}")
        if endpoint.get("method") not in {"GET", "POST"}:
            errors.append(f"{endpoint_class} method must be GET or POST")
        if not isinstance(endpoint.get("path"), str) or not endpoint["path"].startswith("/"):
            errors.append(f"{endpoint_class} path must start with /")
        _require_numeric(endpoint, "p95_threshold_ms", errors, str(endpoint_class))
        _require_numeric(endpoint, "weight", errors, str(endpoint_class))

    errors.extend(validate_no_secret_like_values(plan, "perf_baseline_plan.json"))
    return errors


def _schema_required(schema: dict[str, Any], path: list[str]) -> set[str]:
    node: Any = schema
    for segment in path:
        node = node[segment]
    required = node.get("required")
    return set(required) if isinstance(required, list) else set()


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != ROOT_REQUIRED_FIELDS:
        errors.append("API gateway evidence schema root required fields drifted")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return errors + ["API gateway evidence schema properties must be an object"]
    environment = properties.get("environment")
    if not isinstance(environment, dict) or environment.get("const") != "staging-api-gateway":
        errors.append("API gateway evidence schema environment must be staging-api-gateway")
    profile = properties.get("profile")
    if not isinstance(profile, dict) or profile.get("const") != "gateway_baseline":
        errors.append("API gateway evidence schema profile must be gateway_baseline")
    artifacts_required = _schema_required(schema, ["properties", "artifacts"])
    if artifacts_required != ARTIFACT_FIELDS:
        errors.append("API gateway evidence schema artifact fields drifted")
    endpoint_required = _schema_required(schema, ["$defs", "endpointResult"])
    if endpoint_required != ENDPOINT_REQUIRED_FIELDS:
        errors.append("API gateway evidence schema endpoint metric fields drifted")
    artifact_pattern = schema["$defs"]["artifactPath"]["pattern"]
    if (
        "reports/api-gateway-perf" not in artifact_pattern
        or "\\.(html|json|png)" not in artifact_pattern
    ):
        errors.append("API gateway artifact schema must restrict reports/api-gateway-perf")
    if "(?!.*\\.\\.)" not in artifact_pattern:
        errors.append("API gateway artifact schema must reject traversal segments")
    errors.extend(validate_no_secret_like_values(schema, "evidence_manifest.schema.json"))
    return errors


def validate_locustfile(path: Path = LOCUSTFILE_PATH) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    required_helpers = {
        "load_plan",
        "endpoint_classes_from_env",
        "selected_endpoints",
        "request_interval_seconds",
        "build_request_spec",
    }
    missing = required_helpers - functions
    if missing:
        errors.append("api gateway locustfile missing helpers: " + ", ".join(sorted(missing)))
    for marker in (
        "API_GATEWAY_PERF_JWT",
        "API_GATEWAY_PERF_ENDPOINT_CLASSES",
        "api_gateway/",
        "business_demo",
        "DEMO_LP_PAYLOAD",
    ):
        if marker not in text:
            errors.append(f"api gateway locustfile missing marker {marker}")
    errors.extend(validate_no_secret_like_values({"locustfile": text}, "locustfile.py"))
    return errors


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _artifact_path_errors(
    path_value: str,
    run_id: str,
    source: str,
    artifact_key: str,
) -> list[str]:
    errors: list[str] = []
    if "://" in path_value:
        errors.append(f"{source} artifact path must not be a URL: {path_value}")
    if path_value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", path_value):
        errors.append(f"{source} artifact path must be repository-relative: {path_value}")
    normalized = Path(path_value)
    if ".." in normalized.parts:
        errors.append(f"{source} artifact path must not traverse directories: {path_value}")
    required_prefix = f"reports/api-gateway-perf/{run_id}/"
    if not path_value.startswith(required_prefix):
        errors.append(f"{source} artifact path must stay under {required_prefix}: {path_value}")
    suffix = Path(path_value).suffix.lower()
    if artifact_key == "locust_report" and suffix not in {".html", ".json"}:
        errors.append(f"{source} Locust report must be .html or .json: {path_value}")
    if artifact_key == "grafana_dashboard" and suffix != ".png":
        errors.append(f"{source} Grafana dashboard must be .png: {path_value}")
    if artifact_key in {"prometheus_snapshot", "latency_summary"} and suffix != ".json":
        errors.append(f"{source} {artifact_key} must be .json: {path_value}")
    return errors


def _plan_endpoint_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    endpoints = plan.get("endpoints", [])
    if not isinstance(endpoints, list):
        return {}
    return {
        endpoint["endpoint_class"]: endpoint
        for endpoint in endpoints
        if isinstance(endpoint, dict) and isinstance(endpoint.get("endpoint_class"), str)
    }


def validate_manifest(
    manifest: dict[str, Any],
    plan: dict[str, Any],
    plan_hash: str,
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str):
        return [f"{source} run_id must be a string"]
    if manifest.get("source_story") != "M3.6d":
        errors.append(f"{source} source_story must be M3.6d")
    if manifest.get("environment") != "staging-api-gateway":
        errors.append(f"{source} environment must be staging-api-gateway")
    if manifest.get("profile") != "gateway_baseline":
        errors.append(f"{source} profile must be gateway_baseline")
    if manifest.get("plan_sha256") != plan_hash:
        errors.append(f"{source} plan_sha256 does not match perf baseline plan")

    example_only = manifest.get("example_only")
    if real_evidence and example_only is not False:
        errors.append(f"{source} real API gateway evidence must set example_only=false")
    if not real_evidence and example_only is not True:
        errors.append(f"{source} example API gateway manifest must set example_only=true")

    for path, value in _walk_values(manifest):
        if any(path.endswith(f".{claim}") for claim in FORBIDDEN_PASS_CLAIMS) and value:
            errors.append(f"{source} API gateway evidence cannot claim unrelated pass status")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append(f"{source} artifacts must be an object")
    else:
        if set(artifacts) != ARTIFACT_FIELDS:
            errors.append(f"{source} artifact fields drifted")
        for artifact_key in sorted(ARTIFACT_FIELDS & set(artifacts)):
            value = artifacts.get(artifact_key)
            if not isinstance(value, str):
                errors.append(f"{source} {artifact_key} must be a string")
            else:
                errors.extend(
                    _artifact_path_errors(value, run_id, f"{source} {artifact_key}", artifact_key)
                )

    started = _parse_utc_timestamp(manifest.get("started_utc"))
    ended = _parse_utc_timestamp(manifest.get("ended_utc"))
    duration = manifest.get("duration_seconds")
    if started is None or ended is None:
        errors.append(f"{source} started_utc and ended_utc must be valid")
    elif ended <= started:
        errors.append(f"{source} ended_utc must be after started_utc")
    elif isinstance(duration, int | float):
        expected_duration = (ended - started).total_seconds()
        if duration != expected_duration:
            errors.append(f"{source} duration_seconds must match timestamps")
    if real_evidence and isinstance(duration, int | float) and duration < 1800:
        errors.append(f"{source} duration_seconds fails threshold")

    endpoint_results = manifest.get("endpoint_results")
    if not isinstance(endpoint_results, list):
        return errors + [f"{source} endpoint_results must be a list"]
    endpoint_classes = [
        result.get("endpoint_class") for result in endpoint_results if isinstance(result, dict)
    ]
    if sorted(endpoint_classes) != sorted(ENDPOINT_CLASSES) or len(endpoint_classes) != len(
        set(endpoint_classes)
    ):
        errors.append(f"{source} endpoint classes must match plan exactly")

    plan_by_class = _plan_endpoint_map(plan)
    for result in endpoint_results:
        if not isinstance(result, dict):
            errors.append(f"{source} endpoint result must be an object")
            continue
        endpoint_class = result.get("endpoint_class")
        if endpoint_class not in plan_by_class:
            continue
        plan_endpoint = plan_by_class[str(endpoint_class)]
        comparisons = {
            "method": plan_endpoint.get("method"),
            "path": plan_endpoint.get("path"),
            "auth_mode": plan_endpoint.get("auth_mode"),
            "threshold_p95_ms": plan_endpoint.get("p95_threshold_ms"),
        }
        for key, expected in comparisons.items():
            if result.get(key) != expected:
                errors.append(f"{source} {endpoint_class} {key} must match plan")
        for numeric_key in (
            "request_count",
            "success_count",
            "http_error_rate",
            "locust_p50_ms",
            "locust_p95_ms",
            "locust_p99_ms",
            "prometheus_histogram_quantile_p95_ms",
            "threshold_p95_ms",
        ):
            _require_numeric(result, numeric_key, errors, f"{source} {endpoint_class}")
        if isinstance(result.get("request_count"), int | float) and result["request_count"] <= 0:
            errors.append(f"{source} {endpoint_class} request_count must be greater than 0")
        if (
            isinstance(result.get("success_count"), int | float)
            and isinstance(result.get("request_count"), int | float)
            and result["success_count"] > result["request_count"]
        ):
            errors.append(f"{source} {endpoint_class} success_count exceeds request_count")
        if real_evidence:
            threshold = result.get("threshold_p95_ms")
            if isinstance(threshold, int | float):
                if (
                    isinstance(result.get("locust_p95_ms"), int | float)
                    and result["locust_p95_ms"] >= threshold
                ):
                    errors.append(f"{source} {endpoint_class} locust_p95_ms fails threshold")
                prometheus_key = "prometheus_histogram_quantile_p95_ms"
                if (
                    isinstance(result.get(prometheus_key), int | float)
                    and result[prometheus_key] >= threshold
                ):
                    errors.append(f"{source} {endpoint_class} {prometheus_key} fails threshold")
            if (
                isinstance(result.get("http_error_rate"), int | float)
                and result["http_error_rate"] > 0.01
            ):
                errors.append(f"{source} {endpoint_class} http_error_rate fails threshold")

        for metric_key in result:
            if metric_key.endswith("_seconds"):
                errors.append(f"{source} {endpoint_class} metric {metric_key} must use ms fields")

    errors.extend(validate_no_secret_like_values(manifest, source))
    return errors


def validate_evidence_path_mode(path: Path) -> list[str]:
    relative = path.as_posix()
    expected = "reports/api-gateway-perf/"
    if not relative.startswith(expected) or not relative.endswith("/evidence_manifest.json"):
        return [
            "API gateway evidence path must be "
            "reports/api-gateway-perf/<run_id>/evidence_manifest.json"
        ]
    return []


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    plan = load_json(PLAN_PATH)
    schema = load_json(SCHEMA_PATH)
    example_manifest = load_json(EXAMPLE_MANIFEST_PATH)

    if not isinstance(plan, dict):
        return ["perf_baseline_plan.json must contain an object"]
    plan_hash = canonical_sha256(plan)
    errors.extend(validate_plan(plan))
    if not isinstance(schema, dict):
        errors.append("evidence_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_schema(schema))
    if not isinstance(example_manifest, dict):
        errors.append("evidence_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_manifest(
                example_manifest,
                plan,
                plan_hash,
                source="evidence_manifest.example.json",
                real_evidence=False,
            )
        )
    errors.extend(validate_locustfile())

    if evidence_path is not None:
        evidence = load_json(evidence_path)
        if not isinstance(evidence, dict):
            errors.append(f"{evidence_path} must contain an object")
        else:
            try:
                relative = evidence_path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
            except ValueError:
                relative = evidence_path.as_posix()
                errors.append("--evidence path must be inside the repository")
            errors.extend(validate_evidence_path_mode(Path(relative)))
            errors.extend(
                validate_manifest(
                    evidence,
                    plan,
                    plan_hash,
                    source=relative,
                    real_evidence=True,
                )
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Optional real evidence manifest under reports/api-gateway-perf/<run_id>/",
    )
    args = parser.parse_args(argv)

    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("api gateway perf plan OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
