"""Validate M3.6e production traffic replay infrastructure assets.

The validator is static by default. It validates future sanitized capture
fixtures and replay evidence only when explicit paths are passed.
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
TRAFFIC_REPLAY_DIR = REPO_ROOT / "tools" / "traffic_replay"
PLAN_PATH = TRAFFIC_REPLAY_DIR / "replay_plan.json"
CAPTURE_SCHEMA_PATH = TRAFFIC_REPLAY_DIR / "capture_fixture.schema.json"
CAPTURE_EXAMPLE_PATH = TRAFFIC_REPLAY_DIR / "capture_fixture.example.json"
EVIDENCE_SCHEMA_PATH = TRAFFIC_REPLAY_DIR / "evidence_manifest.schema.json"
EVIDENCE_EXAMPLE_PATH = TRAFFIC_REPLAY_DIR / "evidence_manifest.example.json"

LANES = ("api_gateway_public", "chat_streaming", "contract_fuzz")
ARTIFACT_FIELDS = {
    "replay_report",
    "redaction_audit",
    "contract_seed_report",
    "latency_summary",
}
EXPECTED_LANES: dict[str, dict[str, str]] = {
    "api_gateway_public": {
        "target_service_class": "api-gateway",
        "threshold_reference": "M3.6d",
    },
    "chat_streaming": {
        "target_service_class": "chat-service",
        "threshold_reference": "M3.6a",
    },
    "contract_fuzz": {
        "target_service_class": "contract-tests",
        "threshold_reference": "M3.2",
    },
}
CAPTURE_ROOT_REQUIRED = {
    "dataset_version",
    "source_story",
    "example_only",
    "capture_id",
    "redaction_profile",
    "generated_by",
    "captured_window",
    "requests",
}
CAPTURE_REQUEST_REQUIRED = {
    "request_id",
    "lane",
    "method",
    "path_template",
    "query_shape",
    "body_shape",
    "header_shape",
    "expected_status_family",
    "weight",
}
EVIDENCE_ROOT_REQUIRED = {
    "source_story",
    "example_only",
    "run_id",
    "commit_sha",
    "environment",
    "plan_sha256",
    "capture_fixture_sha256",
    "capture_id",
    "redaction_profile",
    "started_utc",
    "ended_utc",
    "duration_seconds",
    "lane_results",
    "artifacts",
}
LANE_RESULT_REQUIRED = {
    "lane",
    "request_count",
    "success_count",
    "http_error_rate",
    "p95_ms",
    "replay_drift_rate",
    "redaction_violation_count",
    "threshold_reference",
}
FORBIDDEN_PASS_CLAIMS = {
    "g6_hard_gate_pass",
    "api_gateway_perf_pass",
    "chat_load_pass",
    "hard_gate_pass",
    "staging_pass",
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
    "session",
    "password",
    "secret",
    "api_key",
    "private_key",
    "access_key",
    "tenant_id",
    "user_id",
    "phone",
    "email",
    "ip",
    "ip_address",
    "prompt",
}
SECRET_KEY_PATTERN = re.compile(
    r"(^|[_-])(secret|password|private[_-]?key|access[_-]?key|api[_-]?key|bearer|"
    r"tenant[_-]?id|user[_-]?id|cookie|phone|email|prompt|ip[_-]?address)([_-]|$)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = {
    "bearer token": re.compile(r"bearer\s+[a-z0-9._~+/=-]{12,}", re.IGNORECASE),
    "api key assignment": re.compile(
        r"(api[_-]?key|token|secret)\s*[:=]\s*[a-z0-9._~+/=-]{12,}", re.IGNORECASE
    ),
    "generic sk key": re.compile(r"\bsk-[a-zA-Z0-9]{16,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    "credentialed url": re.compile(r"https?://[^/\s:@]+:[^/\s:@]+@"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone number": re.compile(r"\b(?:\+?86[- ]?)?1[3-9]\d{9}\b"),
    "ip address": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
}


def _normalize_key(key: Any) -> str:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).lower()
    return normalized.replace("-", "_")


def _validate_object_fields(
    data: dict[str, Any],
    *,
    required: set[str],
    allowed: set[str],
    source: str,
    label: str = "",
) -> list[str]:
    errors: list[str] = []
    prefix = f"{label} " if label else ""
    for key in sorted(required - set(data)):
        errors.append(f"{source} {prefix}missing required field {key}")
    for key in sorted(set(data) - allowed):
        errors.append(f"{source} {prefix}unexpected field {key}")
    return errors


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


def validate_no_sensitive_values(data: Any, source: str) -> list[str]:
    errors: list[str] = []
    for path, value in _walk_values(data):
        if isinstance(value, dict):
            for key in value:
                normalized_key = _normalize_key(key)
                if normalized_key in SECRET_KEY_EXACT or SECRET_KEY_PATTERN.search(str(key)):
                    if normalized_key == "prompt_redacted":
                        continue
                    label = "prompt-like key" if "prompt" in normalized_key else "secret-like key"
                    errors.append(f"{source} contains forbidden {label} at {path}.{key}")
        if isinstance(value, str):
            if path == "$.$schema":
                continue
            for label, pattern in SECRET_VALUE_PATTERNS.items():
                if pattern.search(value):
                    errors.append(f"{source} contains forbidden {label} at {path}")
            if value.startswith(("http://", "https://")):
                errors.append(f"{source} contains forbidden raw URL host at {path}")
    return errors


def _require_numeric(data: dict[str, Any], key: str, errors: list[str], source: str) -> None:
    if not isinstance(data.get(key), int | float):
        errors.append(f"{source} {key} must be numeric")


def _schema_required(schema: dict[str, Any], path: list[str]) -> set[str]:
    node: Any = schema
    for segment in path:
        node = node[segment]
    required = node.get("required")
    return set(required) if isinstance(required, list) else set()


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_values: dict[str, Any] = {
        "dataset_version": "prod_traffic_replay_plan_v1",
        "source_story": "M3.6e",
        "source_gap": "G6",
        "source_decision": "RE2-7",
        "evidence_directory": "reports/prod-traffic-replay",
        "replay_mode": "sanitized_contract_replay",
        "capture_source": "production_logs_redacted_export",
        "redaction_required": True,
        "sampling_strategy": "deterministic_hash_bucket",
        "replay_environment": "staging",
    }
    for key, expected in expected_values.items():
        if plan.get(key) != expected:
            errors.append(f"replay_plan.json {key} must be {expected}")
    lanes = plan.get("lanes")
    if not isinstance(lanes, list):
        return errors + ["replay_plan.json lanes must be a list"]
    if [lane.get("lane") for lane in lanes if isinstance(lane, dict)] != [*LANES]:
        errors.append(
            "replay_plan.json lane order must be api_gateway_public, chat_streaming, contract_fuzz"
        )
    for lane in lanes:
        if not isinstance(lane, dict):
            errors.append("replay_plan.json lane must be an object")
            continue
        lane_name = lane.get("lane")
        if lane_name not in EXPECTED_LANES:
            errors.append(f"unexpected replay lane {lane_name}")
            continue
        for key, expected in EXPECTED_LANES[str(lane_name)].items():
            if lane.get(key) != expected:
                errors.append(f"{lane_name} {key} must be {expected}")
    errors.extend(validate_no_sensitive_values(plan, "replay_plan.json"))
    return errors


def validate_capture_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != CAPTURE_ROOT_REQUIRED:
        errors.append("capture fixture schema root required fields drifted")
    request_required = _schema_required(schema, ["$defs", "requestShape"])
    if request_required != CAPTURE_REQUEST_REQUIRED:
        errors.append("capture fixture schema request required fields drifted")
    pattern = schema["$defs"]["pathTemplate"]["pattern"]
    if "(?!.*https?://)" not in pattern:
        errors.append("capture fixture schema pathTemplate must reject raw hosts")
    errors.extend(validate_no_sensitive_values(schema, "capture_fixture.schema.json"))
    return errors


def validate_evidence_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _schema_required(schema, []) != EVIDENCE_ROOT_REQUIRED:
        errors.append("evidence schema root required fields drifted")
    lane_required = _schema_required(schema, ["$defs", "laneResult"])
    if lane_required != LANE_RESULT_REQUIRED:
        errors.append("evidence schema lane result fields drifted")
    artifacts_required = _schema_required(schema, ["properties", "artifacts"])
    if artifacts_required != ARTIFACT_FIELDS:
        errors.append("evidence schema artifact fields drifted")
    pattern = schema["$defs"]["artifactPath"]["pattern"]
    if "reports/prod-traffic-replay" not in pattern:
        errors.append("evidence artifact schema must restrict reports/prod-traffic-replay")
    if "(?!.*\\.\\.)" not in pattern:
        errors.append("evidence artifact schema must reject traversal")
    errors.extend(validate_no_sensitive_values(schema, "evidence_manifest.schema.json"))
    return errors


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def validate_capture_fixture(
    capture: dict[str, Any],
    *,
    source: str,
    real_fixture: bool = False,
) -> list[str]:
    errors: list[str] = []
    errors.extend(
        _validate_object_fields(
            capture,
            required=CAPTURE_ROOT_REQUIRED,
            allowed=CAPTURE_ROOT_REQUIRED,
            source=source,
        )
    )
    if capture.get("dataset_version") != "prod_traffic_replay_capture_v1":
        errors.append(f"{source} dataset_version must be prod_traffic_replay_capture_v1")
    if capture.get("source_story") != "M3.6e":
        errors.append(f"{source} source_story must be M3.6e")
    example_only = capture.get("example_only")
    if real_fixture and example_only is not False:
        errors.append(f"{source} real capture fixture must set example_only=false")
    if not real_fixture and example_only is not True:
        errors.append(f"{source} example capture fixture must set example_only=true")
    if real_fixture and capture.get("redaction_profile") == "synthetic-example-no-production-data":
        errors.append(f"{source} real capture fixture must not use synthetic example profile")
    window = capture.get("captured_window")
    if not isinstance(window, dict):
        errors.append(f"{source} captured_window must be an object")
    else:
        started = _parse_utc_timestamp(window.get("started_utc"))
        ended = _parse_utc_timestamp(window.get("ended_utc"))
        if started is None or ended is None:
            errors.append(f"{source} captured window timestamps must be valid")
        elif ended <= started:
            errors.append(f"{source} captured_window ended_utc must be after started_utc")
    requests = capture.get("requests")
    if not isinstance(requests, list):
        return errors + [f"{source} requests must be a list"]
    lanes_seen = set()
    for request in requests:
        if not isinstance(request, dict):
            errors.append(f"{source} request must be an object")
            continue
        errors.extend(
            _validate_object_fields(
                request,
                required=CAPTURE_REQUEST_REQUIRED,
                allowed=CAPTURE_REQUEST_REQUIRED,
                source=source,
                label="request",
            )
        )
        lane = request.get("lane")
        if lane not in LANES:
            errors.append(f"{source} request lane must be one of {', '.join(LANES)}")
        else:
            lanes_seen.add(lane)
        path_template = request.get("path_template")
        if not isinstance(path_template, str) or not path_template.startswith("/"):
            if isinstance(path_template, str) and "://" in path_template:
                errors.append(f"{source} path_template must not contain a host")
            else:
                errors.append(f"{source} path_template must start with /")
        elif "://" in path_template:
            errors.append(f"{source} path_template must not contain a host")
        for key in ("query_shape", "body_shape", "header_shape"):
            if not isinstance(request.get(key), dict):
                errors.append(f"{source} {key} must be an object")
        _require_numeric(request, "weight", errors, source)
    if lanes_seen != set(LANES):
        errors.append(f"{source} capture fixture must include all replay lanes")
    errors.extend(validate_no_sensitive_values(capture, source))
    return errors


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
    required_prefix = f"reports/prod-traffic-replay/{run_id}/"
    if not path_value.startswith(required_prefix):
        errors.append(f"{source} artifact path must stay under {required_prefix}: {path_value}")
    suffix = Path(path_value).suffix.lower()
    if artifact_key == "replay_report" and suffix not in {".html", ".json"}:
        errors.append(f"{source} replay_report must be .html or .json: {path_value}")
    if artifact_key != "replay_report" and suffix != ".json":
        errors.append(f"{source} {artifact_key} must be .json: {path_value}")
    return errors


def _plan_lane_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lanes = plan.get("lanes", [])
    if not isinstance(lanes, list):
        return {}
    return {
        lane["lane"]: lane
        for lane in lanes
        if isinstance(lane, dict) and isinstance(lane.get("lane"), str)
    }


def validate_evidence_manifest(
    evidence: dict[str, Any],
    plan: dict[str, Any],
    capture: dict[str, Any],
    plan_hash: str,
    capture_hash: str,
    *,
    source: str,
    real_evidence: bool,
) -> list[str]:
    errors: list[str] = []
    errors.extend(
        _validate_object_fields(
            evidence,
            required=EVIDENCE_ROOT_REQUIRED,
            allowed=EVIDENCE_ROOT_REQUIRED | FORBIDDEN_PASS_CLAIMS,
            source=source,
        )
    )
    run_id = evidence.get("run_id")
    if not isinstance(run_id, str):
        return [f"{source} run_id must be a string"]
    if evidence.get("source_story") != "M3.6e":
        errors.append(f"{source} source_story must be M3.6e")
    if evidence.get("environment") != "staging-traffic-replay":
        errors.append(f"{source} environment must be staging-traffic-replay")
    if evidence.get("plan_sha256") != plan_hash:
        errors.append(f"{source} plan_sha256 does not match replay plan")
    if evidence.get("capture_fixture_sha256") != capture_hash:
        errors.append(f"{source} capture_fixture_sha256 does not match capture fixture")
    if evidence.get("capture_id") != capture.get("capture_id"):
        errors.append(f"{source} capture_id must match capture fixture")
    if evidence.get("redaction_profile") != capture.get("redaction_profile"):
        errors.append(f"{source} redaction_profile must match capture fixture")
    example_only = evidence.get("example_only")
    if real_evidence and example_only is not False:
        errors.append(f"{source} real replay evidence must set example_only=false")
    if not real_evidence and example_only is not True:
        errors.append(f"{source} example replay evidence must set example_only=true")
    for path, value in _walk_values(evidence):
        if any(path.endswith(f".{claim}") for claim in FORBIDDEN_PASS_CLAIMS) and value:
            errors.append(f"{source} replay evidence cannot claim unrelated pass status")

    started = _parse_utc_timestamp(evidence.get("started_utc"))
    ended = _parse_utc_timestamp(evidence.get("ended_utc"))
    duration = evidence.get("duration_seconds")
    if started is None or ended is None:
        errors.append(f"{source} started_utc and ended_utc must be valid")
    elif ended <= started:
        errors.append(f"{source} ended_utc must be after started_utc")
    elif isinstance(duration, int | float) and duration != (ended - started).total_seconds():
        errors.append(f"{source} duration_seconds must match timestamps")
    if isinstance(duration, int | float) and duration <= 0:
        errors.append(f"{source} duration_seconds must be greater than 0")

    artifacts = evidence.get("artifacts")
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

    lane_results = evidence.get("lane_results")
    if not isinstance(lane_results, list):
        return errors + [f"{source} lane_results must be a list"]
    lane_names = [result.get("lane") for result in lane_results if isinstance(result, dict)]
    if sorted(lane_names) != sorted(LANES) or len(lane_names) != len(set(lane_names)):
        errors.append(f"{source} lane results must match plan exactly")
    plan_by_lane = _plan_lane_map(plan)
    for index, result in enumerate(lane_results):
        if not isinstance(result, dict):
            errors.append(f"{source} lane result must be an object")
            continue
        errors.extend(
            _validate_object_fields(
                result,
                required=LANE_RESULT_REQUIRED,
                allowed=LANE_RESULT_REQUIRED,
                source=source,
                label="lane result",
            )
        )
        lane = result.get("lane")
        lane_label = (
            str(lane) if lane in plan_by_lane else LANES[index] if index < len(LANES) else str(lane)
        )
        plan_lane = plan_by_lane.get(str(lane))
        if plan_lane is not None and result.get("threshold_reference") != plan_lane.get(
            "threshold_reference"
        ):
            errors.append(f"{source} {lane_label} threshold_reference must match plan")
        for key in (
            "request_count",
            "success_count",
            "http_error_rate",
            "p95_ms",
            "replay_drift_rate",
            "redaction_violation_count",
        ):
            _require_numeric(result, key, errors, f"{source} {lane_label}")
        if isinstance(result.get("request_count"), int | float) and result["request_count"] <= 0:
            errors.append(f"{source} {lane_label} request_count must be greater than 0")
        if (
            isinstance(result.get("success_count"), int | float)
            and isinstance(result.get("request_count"), int | float)
            and result["success_count"] > result["request_count"]
        ):
            errors.append(f"{source} {lane_label} success_count exceeds request_count")
        if result.get("redaction_violation_count", 0) > 0:
            errors.append(f"{source} {lane_label} redaction_violation_count must be 0")
        if real_evidence:
            if (
                isinstance(result.get("replay_drift_rate"), int | float)
                and result["replay_drift_rate"] > 0.02
            ):
                errors.append(f"{source} {lane_label} replay_drift_rate fails threshold")
            error_rate_limit = 0.02 if lane_label == "chat_streaming" else 0.01
            if (
                isinstance(result.get("http_error_rate"), int | float)
                and result["http_error_rate"] > error_rate_limit
            ):
                errors.append(f"{source} {lane_label} http_error_rate fails threshold")
        for key in result:
            if key.endswith("_seconds"):
                errors.append(f"{source} {lane_label} metric {key} must use ms fields")
    errors.extend(validate_no_sensitive_values(evidence, source))
    return errors


def validate_capture_path_mode(path: Path) -> list[str]:
    relative = path.as_posix()
    if not relative.startswith("reports/prod-traffic-replay/") or not relative.endswith(
        "/capture_fixture.json"
    ):
        return [
            "traffic replay capture fixture path must be "
            "reports/prod-traffic-replay/<run_id>/capture_fixture.json"
        ]
    return []


def validate_evidence_path_mode(path: Path) -> list[str]:
    relative = path.as_posix()
    if not relative.startswith("reports/prod-traffic-replay/") or not relative.endswith(
        "/evidence_manifest.json"
    ):
        return [
            "traffic replay evidence path must be "
            "reports/prod-traffic-replay/<run_id>/evidence_manifest.json"
        ]
    return []


def _repo_relative(path: Path, flag: str, errors: list[str]) -> Path:
    try:
        return Path(path.resolve().relative_to(REPO_ROOT.resolve()).as_posix())
    except ValueError:
        errors.append(f"{flag} path must be inside the repository")
        return Path(path.as_posix())


def validate_all(
    capture_fixture_path: Path | None = None,
    evidence_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    plan = load_json(PLAN_PATH)
    capture_schema = load_json(CAPTURE_SCHEMA_PATH)
    capture_example = load_json(CAPTURE_EXAMPLE_PATH)
    evidence_schema = load_json(EVIDENCE_SCHEMA_PATH)
    evidence_example = load_json(EVIDENCE_EXAMPLE_PATH)
    if not isinstance(plan, dict):
        return ["replay_plan.json must contain an object"]
    if not isinstance(capture_example, dict):
        return ["capture_fixture.example.json must contain an object"]
    plan_hash = canonical_sha256(plan)
    capture_example_hash = canonical_sha256(capture_example)

    errors.extend(validate_plan(plan))
    if not isinstance(capture_schema, dict):
        errors.append("capture_fixture.schema.json must contain an object")
    else:
        errors.extend(validate_capture_schema(capture_schema))
    errors.extend(validate_capture_fixture(capture_example, source="capture_fixture.example.json"))
    if not isinstance(evidence_schema, dict):
        errors.append("evidence_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_evidence_schema(evidence_schema))
    if not isinstance(evidence_example, dict):
        errors.append("evidence_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_evidence_manifest(
                evidence_example,
                plan,
                capture_example,
                plan_hash,
                capture_example_hash,
                source="evidence_manifest.example.json",
                real_evidence=False,
            )
        )

    capture_for_evidence = capture_example
    capture_hash_for_evidence = capture_example_hash
    if capture_fixture_path is not None:
        relative = _repo_relative(capture_fixture_path, "--capture-fixture", errors)
        errors.extend(validate_capture_path_mode(relative))
        capture_fixture = load_json(capture_fixture_path)
        if not isinstance(capture_fixture, dict):
            errors.append(f"{capture_fixture_path} must contain an object")
        else:
            errors.extend(
                validate_capture_fixture(
                    capture_fixture,
                    source=relative.as_posix(),
                    real_fixture=True,
                )
            )
            capture_for_evidence = capture_fixture
            capture_hash_for_evidence = canonical_sha256(capture_fixture)

    if evidence_path is not None:
        relative = _repo_relative(evidence_path, "--evidence", errors)
        errors.extend(validate_evidence_path_mode(relative))
        if capture_fixture_path is None:
            sibling_capture = evidence_path.parent / "capture_fixture.json"
            if not sibling_capture.exists():
                errors.append("--evidence matching capture_fixture.json is required")
            else:
                capture_fixture = load_json(sibling_capture)
                if not isinstance(capture_fixture, dict):
                    errors.append(f"{sibling_capture} must contain an object")
                else:
                    capture_for_evidence = capture_fixture
                    capture_hash_for_evidence = canonical_sha256(capture_fixture)
                    sibling_relative = _repo_relative(sibling_capture, "--capture-fixture", errors)
                    errors.extend(validate_capture_path_mode(sibling_relative))
                    errors.extend(
                        validate_capture_fixture(
                            capture_fixture,
                            source=sibling_relative.as_posix(),
                            real_fixture=True,
                        )
                    )
        evidence = load_json(evidence_path)
        if not isinstance(evidence, dict):
            errors.append(f"{evidence_path} must contain an object")
        else:
            errors.extend(
                validate_evidence_manifest(
                    evidence,
                    plan,
                    capture_for_evidence,
                    plan_hash,
                    capture_hash_for_evidence,
                    source=relative.as_posix(),
                    real_evidence=True,
                )
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture-fixture",
        type=Path,
        help="Optional sanitized capture fixture under reports/prod-traffic-replay/<run_id>/",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Optional replay evidence manifest under reports/prod-traffic-replay/<run_id>/",
    )
    args = parser.parse_args(argv)

    errors = validate_all(args.capture_fixture, args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("traffic replay plan OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
