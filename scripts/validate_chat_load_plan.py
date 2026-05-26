"""Validate M3.6a/M3.6b/M3.6c Chat load-test plan assets.

The validator is static by default. It validates real operator evidence only
when an explicit evidence manifest is passed with --evidence or
--single-node-evidence or --incident-fallback-evidence.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CHAT_LOAD_DIR = REPO_ROOT / "tools" / "chat_load"
PROMPTS_PATH = CHAT_LOAD_DIR / "prompts_v1.json"
PROFILES_PATH = CHAT_LOAD_DIR / "staging_profiles.json"
LOCUSTFILE_PATH = CHAT_LOAD_DIR / "locustfile.py"
SCHEMA_PATH = CHAT_LOAD_DIR / "evidence_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = CHAT_LOAD_DIR / "evidence_manifest.example.json"
SINGLE_NODE_PROFILES_PATH = CHAT_LOAD_DIR / "single_node_profiles.json"
SINGLE_NODE_LOCUSTFILE_PATH = CHAT_LOAD_DIR / "single_node_locustfile.py"
SINGLE_NODE_SCHEMA_PATH = CHAT_LOAD_DIR / "single_node_evidence_manifest.schema.json"
SINGLE_NODE_EXAMPLE_MANIFEST_PATH = CHAT_LOAD_DIR / "single_node_evidence_manifest.example.json"
INCIDENT_FALLBACK_PLAN_PATH = CHAT_LOAD_DIR / "incident_fallback_plan.json"
INCIDENT_FALLBACK_SCHEMA_PATH = CHAT_LOAD_DIR / "incident_fallback_evidence_manifest.schema.json"
INCIDENT_FALLBACK_EXAMPLE_MANIFEST_PATH = (
    CHAT_LOAD_DIR / "incident_fallback_evidence_manifest.example.json"
)
REQUIRED_PROFILES = {"baseline", "stress", "soak"}
SINGLE_NODE_PROFILE = "single_node_baseline"
INCIDENT_FALLBACK_ARTIFACTS = {
    "locust_report",
    "provider_health_snapshot",
    "fallback_decision_log",
    "operator_timeline",
    "latency_snapshot",
}
INCIDENT_FALLBACK_TIMELINE_FIELDS = {
    "incident_started_utc",
    "provider_health_failed_utc",
    "operator_decision_utc",
    "fallback_confirmed_utc",
    "measurement_started_utc",
    "measurement_ended_utc",
}
INCIDENT_FALLBACK_METRICS = {
    "request_count",
    "completed_stream_count",
    "http_error_rate",
    "fallback_route_ratio",
    "switch_duration_seconds",
    "detection_window_seconds",
    "fallback_first_token_p95_ms",
    "fallback_total_response_p95_ms",
    "fallback_streaming_tokens_per_second",
    "schema_parity_pass_count",
    "schema_parity_total_count",
    "fallback_provider_error_count",
}
REQUIRED_CATEGORIES = {
    "optimization",
    "prediction",
    "explanation",
    "file-analysis",
    "what-if",
    "benign-support-chat",
}
REQUIRED_PROMPT_FIELDS = {"id", "locale", "category", "difficulty", "expected_path", "prompt"}
REQUIRED_HELPERS = {
    "load_profiles",
    "selected_profile_name",
    "iter_sse_data_lines",
    "extract_token_units",
    "calculate_stream_metrics",
    "prompt_fixture_sha256",
}
REQUIRED_SINGLE_NODE_HELPERS = {
    "load_single_node_profiles",
    "selected_single_node_profile_name",
    "load_selected_single_node_profile",
    "single_node_endpoint",
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


def prompt_fixture_hash(data: dict[str, Any]) -> str:
    return canonical_sha256(data)


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
    return errors


def validate_prompts(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("dataset_version") != "chat_load_prompts_v1":
        errors.append("prompts_v1.json dataset_version must be chat_load_prompts_v1")
    if data.get("source_story") != "M3.6a":
        errors.append("prompts_v1.json source_story must be M3.6a")
    prompts = data.get("prompts")
    if not isinstance(prompts, list):
        return errors + ["prompts_v1.json prompts must be a list"]
    if data.get("prompt_count") != 100 or len(prompts) != 100:
        errors.append("prompts_v1.json must declare and contain exactly 100 prompts")

    expected_ids = [f"chat-load-v1-{index:03d}" for index in range(1, 101)]
    actual_ids: list[str] = []
    categories: Counter[str] = Counter()
    expected_paths: Counter[str] = Counter()
    locales: Counter[str] = Counter()
    for index, prompt in enumerate(prompts):
        if not isinstance(prompt, dict):
            errors.append(f"prompt #{index + 1} must be an object")
            continue
        missing = REQUIRED_PROMPT_FIELDS - set(prompt)
        extra = set(prompt) - REQUIRED_PROMPT_FIELDS
        if missing:
            errors.append(
                f"{prompt.get('id', f'prompt #{index + 1}')} missing fields: {sorted(missing)}"
            )
        if extra:
            errors.append(
                f"{prompt.get('id', f'prompt #{index + 1}')} has unexpected fields: {sorted(extra)}"
            )
        actual_ids.append(str(prompt.get("id")))
        category = str(prompt.get("category"))
        categories[category] += 1
        expected_path = str(prompt.get("expected_path"))
        expected_paths[expected_path] += 1
        locales[str(prompt.get("locale"))] += 1
        text = prompt.get("prompt")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{prompt.get('id', f'prompt #{index + 1}')} prompt must be non-empty")

    if actual_ids != expected_ids:
        errors.append("prompt IDs must be contiguous chat-load-v1-001 through chat-load-v1-100")
    missing_categories = REQUIRED_CATEGORIES - set(categories)
    if missing_categories:
        errors.append("prompts missing categories: " + ", ".join(sorted(missing_categories)))
    for category in REQUIRED_CATEGORIES:
        if categories[category] < 10:
            errors.append(f"category {category} must contain at least 10 prompts")
    if set(expected_paths) != {"chat_only", "solve_expected"}:
        errors.append("expected_path values must be exactly chat_only and solve_expected")
    if expected_paths["solve_expected"] < 30:
        errors.append("prompts must include at least 30 solve_expected prompts")
    if not {"zh-CN", "en-US", "mixed"}.issubset(locales):
        errors.append("prompts must include zh-CN, en-US, and mixed locales")

    errors.extend(validate_no_secret_like_values(data, "prompts_v1.json"))
    return errors


def _require_numeric(profile: dict[str, Any], key: str, errors: list[str], name: str) -> None:
    value = profile.get(key)
    if not isinstance(value, int | float):
        errors.append(f"profile {name} {key} must be numeric")


def validate_profiles(data: dict[str, Any], expected_hash: str) -> list[str]:
    errors: list[str] = []
    if data.get("dataset_version") != "chat_load_profiles_v1":
        errors.append("staging_profiles.json dataset_version must be chat_load_profiles_v1")
    if data.get("source_story") != "M3.6a":
        errors.append("staging_profiles.json source_story must be M3.6a")
    if data.get("prompt_fixture") != "tools/chat_load/prompts_v1.json":
        errors.append("staging_profiles.json prompt_fixture must reference prompts_v1.json")

    hard_gate = data.get("hard_gate_thresholds")
    if not isinstance(hard_gate, dict):
        errors.append("staging_profiles.json hard_gate_thresholds must be an object")
    else:
        expected = {
            "first_token_p95_max_ms": 3000,
            "streaming_min_tokens_per_second": 20,
            "e2e_solve_p95_max_ms": 90000,
        }
        for key, value in expected.items():
            if hard_gate.get(key) != value:
                errors.append(f"hard_gate_thresholds.{key} must be {value}")

    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        return errors + ["staging_profiles.json profiles must be an object"]
    if set(profiles) != REQUIRED_PROFILES:
        errors.append("profiles must be exactly baseline, stress, and soak")

    expected_profile_values: dict[str, dict[str, Any]] = {
        "baseline": {
            "users": 100,
            "target_rps": 5,
            "effective_requests_per_user_per_minute": 3,
            "first_token_p95_max_ms": 2000,
        },
        "stress": {
            "users": 100,
            "target_rps": 100,
            "effective_requests_per_user_per_minute": 60,
            "run_time_seconds": 1800,
            "first_token_p50_max_ms": 1500,
            "first_token_p95_max_ms": 3000,
            "streaming_min_tokens_per_second": 20,
        },
        "soak": {
            "users": 100,
            "target_rps": 10,
            "effective_requests_per_user_per_minute": 6,
            "run_time_seconds": 43200,
            "streaming_min_tokens_per_second": 20,
            "oom_count_max": 0,
            "deadlock_count_max": 0,
        },
    }

    for name in sorted(REQUIRED_PROFILES & set(profiles)):
        profile = profiles[name]
        if not isinstance(profile, dict):
            errors.append(f"profile {name} must be an object")
            continue
        if profile.get("name") != name:
            errors.append(f"profile {name} name must match key")
        if profile.get("prompt_fixture_sha256") != expected_hash:
            errors.append(f"profile {name} prompt_fixture_sha256 does not match prompts_v1.json")
        for key, value in expected_profile_values[name].items():
            if profile.get(key) != value:
                errors.append(f"profile {name} {key} must be {value}")
        for key in ("users", "target_rps", "effective_requests_per_user_per_minute"):
            _require_numeric(profile, key, errors, name)
        if all(
            isinstance(profile.get(key), int | float)
            for key in ("users", "target_rps", "effective_requests_per_user_per_minute")
        ):
            calculated = (
                float(profile["users"])
                * float(profile["effective_requests_per_user_per_minute"])
                / 60.0
            )
            if abs(calculated - float(profile["target_rps"])) > 0.001:
                errors.append(f"profile {name} RPS math does not match target_rps")
        for key in profile:
            if key.endswith("_seconds") and key.endswith("_ms"):
                errors.append(f"profile {name} has impossible mixed unit field {key}")

    baseline_note = (
        profiles.get("baseline", {}).get("source_note") if isinstance(profiles, dict) else ""
    )
    if not isinstance(baseline_note, str) or "1.67 RPS" not in baseline_note:
        errors.append("baseline source_note must preserve the 1.67 RPS source inconsistency")

    errors.extend(validate_no_secret_like_values(data, "staging_profiles.json"))
    return errors


def validate_single_node_profiles(data: dict[str, Any], expected_hash: str) -> list[str]:
    errors: list[str] = []
    if data.get("dataset_version") != "chat_single_node_profiles_v1":
        errors.append(
            "single_node_profiles.json dataset_version must be chat_single_node_profiles_v1"
        )
    if data.get("source_story") != "M3.6b":
        errors.append("single_node_profiles.json source_story must be M3.6b")
    if data.get("prompt_fixture") != "tools/chat_load/prompts_v1.json":
        errors.append("single_node_profiles.json prompt_fixture must reference prompts_v1.json")

    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        return errors + ["single_node_profiles.json profiles must be an object"]
    if set(profiles) != {SINGLE_NODE_PROFILE}:
        errors.append("single-node profiles must contain only single_node_baseline")

    profile = profiles.get(SINGLE_NODE_PROFILE)
    if not isinstance(profile, dict):
        return errors + ["single_node_baseline profile must be an object"]

    expected_values: dict[str, Any] = {
        "name": SINGLE_NODE_PROFILE,
        "node_count": 1,
        "users": 20,
        "run_time_seconds": 300,
        "target_rps": 2,
        "effective_requests_per_user_per_minute": 6,
        "first_token_p50_max_ms": 1500,
        "first_token_p95_max_ms": 3000,
        "streaming_min_tokens_per_second": 20,
        "e2e_solve_p95_max_ms": 90000,
        "sandbox_startup_p95_max_ms": 100,
        "capability_lookup_p95_max_ms": 20,
        "chat_internal_hop_p95_max_ms": 200,
        "advisory_only": True,
        "hard_gate_candidate": False,
    }
    for key, value in expected_values.items():
        if profile.get(key) != value:
            errors.append(f"single_node_baseline {key} must be {value}")
    if profile.get("prompt_fixture_sha256") != expected_hash:
        errors.append("single_node_baseline prompt_fixture_sha256 does not match prompts_v1.json")
    for key in ("node_count", "users", "target_rps", "effective_requests_per_user_per_minute"):
        _require_numeric(profile, key, errors, SINGLE_NODE_PROFILE)
    if all(
        isinstance(profile.get(key), int | float)
        for key in ("users", "target_rps", "effective_requests_per_user_per_minute")
    ):
        calculated = (
            float(profile["users"]) * float(profile["effective_requests_per_user_per_minute"]) / 60
        )
        if abs(calculated - float(profile["target_rps"])) > 0.001:
            errors.append("single_node_baseline RPS math does not match target_rps")
    for key in profile:
        if key.endswith("_seconds") and key.endswith("_ms"):
            errors.append(f"single_node_baseline has impossible mixed unit field {key}")

    errors.extend(validate_no_secret_like_values(data, "single_node_profiles.json"))
    return errors


def validate_incident_fallback_plan(data: dict[str, Any], expected_hash: str) -> list[str]:
    errors: list[str] = []
    expected_values: dict[str, Any] = {
        "dataset_version": "chat_incident_fallback_plan_v1",
        "source_story": "M3.6c",
        "primary_provider": "deepseek-v3.5",
        "fallback_provider": "qwen-max",
        "simulated_incident_trigger": "provider_health_deepseek_failure",
        "manual_operation": "operator_manual_switch_to_fallback",
        "switch_budget_seconds": 300,
        "fallback_first_token_p95_max_ms": 5000,
        "fallback_route_ratio_min": 1.0,
        "schema_parity_required": True,
        "drill_only": True,
        "evidence_directory": "reports/chat-incident-fallback",
        "prompt_fixture": "tools/chat_load/prompts_v1.json",
        "prompt_count": 100,
    }
    for key, value in expected_values.items():
        if data.get(key) != value:
            errors.append(f"incident_fallback_plan.json {key} must be {value}")
    if data.get("prompt_fixture_sha256") != expected_hash:
        errors.append("incident_fallback_plan.json prompt_fixture_sha256 does not match")
    artifact_fields = data.get("artifact_fields")
    if not isinstance(artifact_fields, list):
        errors.append("incident_fallback_plan.json artifact_fields must be a list")
    elif set(artifact_fields) != INCIDENT_FALLBACK_ARTIFACTS:
        errors.append("incident_fallback_plan.json artifact_fields drifted")
    for key in ("switch_budget_seconds", "fallback_first_token_p95_max_ms"):
        _require_numeric(data, key, errors, "incident_fallback_plan")
    errors.extend(validate_no_secret_like_values(data, "incident_fallback_plan.json"))
    return errors


def validate_locustfile(path: Path = LOCUSTFILE_PATH) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    missing = REQUIRED_HELPERS - functions
    if missing:
        errors.append("locustfile.py missing helper functions: " + ", ".join(sorted(missing)))
    for profile in REQUIRED_PROFILES:
        if profile not in text:
            errors.append(f"locustfile.py must reference profile {profile}")
    for marker in (
        "CHAT_LOAD_PROFILE",
        "CHAT_LOAD_ENDPOINT",
        "first_token_latency_ms",
        "total_response_latency_ms",
        "streaming_tokens_per_second",
        "token_count_method",
        "content_unit_approximation",
    ):
        if marker not in text:
            errors.append(f"locustfile.py missing marker {marker}")
    if "total_response_latency_ms=(completed_at - started_at)" not in text:
        errors.append("locustfile.py must compute total response latency separately")
    if "first_token_latency_ms=(first_token_at - started_at)" not in text:
        errors.append("locustfile.py must compute first-token latency from first token time")
    if "streaming_seconds = max(completed_at - first_token_at" not in text:
        errors.append("locustfile.py must compute streaming throughput after first token")
    errors.extend(validate_no_secret_like_values({"locustfile": text}, "locustfile.py"))
    return errors


def validate_single_node_locustfile(path: Path = SINGLE_NODE_LOCUSTFILE_PATH) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    missing = REQUIRED_SINGLE_NODE_HELPERS - functions
    if missing:
        errors.append(
            "single_node_locustfile.py missing helper functions: " + ", ".join(sorted(missing))
        )
    for marker in (
        "CHAT_SINGLE_NODE_PROFILE",
        "CHAT_LOAD_ENDPOINT",
        "single_node_baseline",
        "calculate_stream_metrics",
        "iter_sse_data_lines",
        "next_prompt",
        "request_interval_seconds",
    ):
        if marker not in text:
            errors.append(f"single_node_locustfile.py missing marker {marker}")
    if "from tools.chat_load.locustfile import" not in text:
        errors.append("single_node_locustfile.py must reuse M3.6a locust helpers")
    if "calculate_stream_metrics(started_at, completed_at, event_records)" not in text:
        errors.append("single_node_locustfile.py must reuse calculate_stream_metrics")
    errors.extend(validate_no_secret_like_values({"single_node_locustfile": text}, str(path.name)))
    return errors


def _schema_required(schema: dict[str, Any], path: list[str]) -> set[str]:
    node: Any = schema
    for segment in path:
        node = node[segment]
    required = node.get("required")
    return set(required) if isinstance(required, list) else set()


def validate_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root_required = _schema_required(schema, [])
    expected_root = {
        "source_story",
        "run_id",
        "example_only",
        "generated_by",
        "commit_sha",
        "cluster",
        "endpoint_path",
        "prompt_fixture",
        "prompt_fixture_sha256",
        "prompt_count",
        "profiles",
    }
    if root_required != expected_root:
        errors.append("evidence schema root required fields drifted")
    profiles_required = set(
        schema["properties"]["profiles"].get("required", [])
        if isinstance(schema.get("properties", {}).get("profiles"), dict)
        else []
    )
    if profiles_required != REQUIRED_PROFILES:
        errors.append("evidence schema must require baseline, stress, and soak")
    metrics_required = _schema_required(
        schema, ["$defs", "profileEvidence", "properties", "metrics"]
    )
    expected_metrics = {
        "request_count",
        "completed_stream_count",
        "first_token_p50_ms",
        "first_token_p95_ms",
        "total_response_p95_ms",
        "streaming_tokens_per_second",
        "token_count_method",
        "http_error_rate",
        "solve_prompt_count",
        "e2e_solve_p95_ms",
        "oom_count",
        "deadlock_count",
    }
    if metrics_required != expected_metrics:
        errors.append("evidence schema metric required fields drifted")
    artifact_pattern = schema["$defs"]["artifactPath"]["pattern"]
    if "reports/chat-load" not in artifact_pattern or "\\.(html|json|png)" not in artifact_pattern:
        errors.append("artifact path schema must restrict reports/chat-load and html/json/png")
    errors.extend(validate_no_secret_like_values(schema, "evidence_manifest.schema.json"))
    return errors


def validate_single_node_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root_required = _schema_required(schema, [])
    expected_root = {
        "source_story",
        "run_id",
        "example_only",
        "generated_by",
        "commit_sha",
        "environment",
        "node_count",
        "endpoint_path",
        "prompt_fixture",
        "prompt_fixture_sha256",
        "prompt_count",
        "profiles",
    }
    if root_required != expected_root:
        errors.append("single-node evidence schema root required fields drifted")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return errors + ["single-node evidence schema properties must be an object"]
    environment = properties.get("environment")
    if not isinstance(environment, dict) or environment.get("const") != "single-node-dev":
        errors.append("single-node evidence schema environment must be single-node-dev")
    node_count = properties.get("node_count")
    if not isinstance(node_count, dict) or node_count.get("const") != 1:
        errors.append("single-node evidence schema node_count must be 1")
    profiles_required = set(
        properties["profiles"].get("required", [])
        if isinstance(properties.get("profiles"), dict)
        else []
    )
    if profiles_required != {SINGLE_NODE_PROFILE}:
        errors.append("single-node evidence schema must require single_node_baseline only")
    metrics_required = _schema_required(
        schema, ["$defs", "profileEvidence", "properties", "metrics"]
    )
    expected_metrics = {
        "request_count",
        "completed_stream_count",
        "first_token_p50_ms",
        "first_token_p95_ms",
        "total_response_p95_ms",
        "streaming_tokens_per_second",
        "token_count_method",
        "http_error_rate",
        "solve_prompt_count",
        "e2e_solve_p95_ms",
        "oom_count",
        "deadlock_count",
        "sandbox_startup_p95_ms",
        "capability_lookup_p95_ms",
        "chat_internal_hop_p95_ms",
    }
    if metrics_required != expected_metrics:
        errors.append("single-node evidence schema metric required fields drifted")
    artifact_pattern = schema["$defs"]["locustReportPath"]["pattern"]
    metrics_pattern = schema["$defs"]["metricsSnapshotPath"]["pattern"]
    if (
        "reports/chat-single-node" not in artifact_pattern
        or "\\.(html|json)" not in artifact_pattern
    ):
        errors.append(
            "single-node artifact schema must restrict reports/chat-single-node html/json"
        )
    if "reports/chat-single-node" not in metrics_pattern or "\\.json" not in metrics_pattern:
        errors.append("single-node metrics snapshot schema must restrict to json")
    errors.extend(
        validate_no_secret_like_values(schema, "single_node_evidence_manifest.schema.json")
    )
    return errors


def validate_incident_fallback_schema(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root_required = _schema_required(schema, [])
    expected_root = {
        "source_story",
        "run_id",
        "example_only",
        "generated_by",
        "commit_sha",
        "environment",
        "endpoint_path",
        "primary_provider",
        "fallback_provider",
        "prompt_fixture",
        "prompt_fixture_sha256",
        "prompt_count",
        "drill_plan_sha256",
        "artifacts",
        "timeline",
        "metrics",
    }
    if root_required != expected_root:
        errors.append("incident fallback evidence schema root required fields drifted")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return errors + ["incident fallback evidence schema properties must be an object"]
    environment = properties.get("environment")
    if not isinstance(environment, dict) or environment.get("const") != "staging-incident-drill":
        errors.append(
            "incident fallback evidence schema environment must be staging-incident-drill"
        )
    primary_provider = properties.get("primary_provider")
    if not isinstance(primary_provider, dict) or primary_provider.get("const") != "deepseek-v3.5":
        errors.append("incident fallback evidence schema primary_provider must be deepseek-v3.5")
    fallback_provider = properties.get("fallback_provider")
    if not isinstance(fallback_provider, dict) or fallback_provider.get("const") != "qwen-max":
        errors.append("incident fallback evidence schema fallback_provider must be qwen-max")
    artifacts_required = _schema_required(schema, ["properties", "artifacts"])
    if artifacts_required != INCIDENT_FALLBACK_ARTIFACTS:
        errors.append("incident fallback evidence schema artifact fields drifted")
    timeline_required = _schema_required(schema, ["$defs", "timeline"])
    if timeline_required != INCIDENT_FALLBACK_TIMELINE_FIELDS:
        errors.append("incident fallback evidence schema timeline fields drifted")
    metrics_required = _schema_required(schema, ["$defs", "metrics"])
    if metrics_required != INCIDENT_FALLBACK_METRICS:
        errors.append("incident fallback evidence schema metric fields drifted")
    locust_pattern = schema["$defs"]["locustReportPath"]["pattern"]
    json_pattern = schema["$defs"]["jsonArtifactPath"]["pattern"]
    if (
        "reports/chat-incident-fallback" not in locust_pattern
        or "\\.(html|json)" not in locust_pattern
    ):
        errors.append("incident fallback locust artifact schema must restrict html/json reports")
    if "reports/chat-incident-fallback" not in json_pattern or "\\.json" not in json_pattern:
        errors.append("incident fallback JSON artifact schema must restrict to json")
    if "(?!.*\\.\\.)" not in locust_pattern or "(?!.*\\.\\.)" not in json_pattern:
        errors.append("incident fallback artifact schema must reject traversal segments")
    errors.extend(
        validate_no_secret_like_values(schema, "incident_fallback_evidence_manifest.schema.json")
    )
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
    required_prefix = f"reports/chat-load/{run_id}/"
    if not path_value.startswith(required_prefix):
        errors.append(f"{source} artifact path must stay under {required_prefix}: {path_value}")
    suffix = Path(path_value).suffix.lower()
    if artifact_key == "grafana_screenshot":
        if suffix != ".png":
            errors.append(f"{source} Grafana screenshot must be .png: {path_value}")
    if artifact_key == "locust_report" and suffix not in {".html", ".json"}:
        errors.append(f"{source} Locust report must be .html or .json: {path_value}")
    return errors


def _single_node_artifact_path_errors(
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
    required_prefix = f"reports/chat-single-node/{run_id}/"
    if not path_value.startswith(required_prefix):
        errors.append(f"{source} artifact path must stay under {required_prefix}: {path_value}")
    suffix = Path(path_value).suffix.lower()
    if artifact_key == "locust_report" and suffix not in {".html", ".json"}:
        errors.append(f"{source} Locust report must be .html or .json: {path_value}")
    if artifact_key == "metrics_snapshot" and suffix != ".json":
        errors.append(f"{source} metrics snapshot must be .json: {path_value}")
    return errors


def _incident_fallback_artifact_path_errors(
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
    required_prefix = f"reports/chat-incident-fallback/{run_id}/"
    if not path_value.startswith(required_prefix):
        errors.append(f"{source} artifact path must stay under {required_prefix}: {path_value}")
    suffix = Path(path_value).suffix.lower()
    if artifact_key == "locust_report" and suffix not in {".html", ".json"}:
        errors.append(f"{source} Locust report must be .html or .json: {path_value}")
    if artifact_key != "locust_report" and suffix != ".json":
        errors.append(f"{source} {artifact_key} must be .json: {path_value}")
    return errors


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def validate_evidence_path_mode(path: Path, mode: str) -> list[str]:
    relative = path.as_posix()
    expected_by_mode = {
        "staging": (
            "reports/chat-load/",
            "--evidence path must be reports/chat-load/<run_id>/evidence_manifest.json",
        ),
        "single-node": (
            "reports/chat-single-node/",
            "--single-node-evidence path must be "
            "reports/chat-single-node/<run_id>/evidence_manifest.json",
        ),
        "incident-fallback": (
            "reports/chat-incident-fallback/",
            "--incident fallback evidence path must be "
            "reports/chat-incident-fallback/<run_id>/evidence_manifest.json",
        ),
    }
    prefix, message = expected_by_mode[mode]
    if not relative.startswith(prefix) or not relative.endswith("/evidence_manifest.json"):
        return [message]
    return []


def validate_manifest(
    manifest: dict[str, Any],
    expected_hash: str,
    *,
    source: str,
    real_evidence: bool,
    profiles_config: dict[str, Any] | None = None,
    hard_gate_config: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str):
        return [f"{source} run_id must be a string"]
    if manifest.get("source_story") != "M3.6a":
        errors.append(f"{source} source_story must be M3.6a")
    if manifest.get("prompt_fixture") != "tools/chat_load/prompts_v1.json":
        errors.append(f"{source} prompt_fixture must reference prompts_v1.json")
    if manifest.get("prompt_fixture_sha256") != expected_hash:
        errors.append(f"{source} prompt_fixture_sha256 does not match prompts_v1.json")
    if manifest.get("prompt_count") != 100:
        errors.append(f"{source} prompt_count must be 100")

    example_only = manifest.get("example_only")
    if real_evidence and example_only is not False:
        errors.append(f"{source} real evidence must set example_only=false")
    if not real_evidence and example_only is not True:
        errors.append(f"{source} example manifest must set example_only=true")

    cluster = manifest.get("cluster")
    if not isinstance(cluster, dict):
        errors.append(f"{source} cluster must be an object")
    else:
        if cluster.get("environment") != "staging":
            errors.append(f"{source} cluster.environment must be staging")
        if cluster.get("node_count") != 5:
            errors.append(f"{source} cluster.node_count must be 5")

    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        return errors + [f"{source} profiles must be an object"]
    if set(profiles) != REQUIRED_PROFILES:
        errors.append(f"{source} profiles must be exactly baseline, stress, and soak")

    for name in sorted(REQUIRED_PROFILES & set(profiles)):
        profile = profiles[name]
        if not isinstance(profile, dict):
            errors.append(f"{source} profile {name} must be an object")
            continue
        if profile.get("profile") != name:
            errors.append(f"{source} profile {name} profile field must match key")
        for artifact_key in ("locust_report", "grafana_screenshot"):
            value = profile.get(artifact_key)
            if not isinstance(value, str):
                errors.append(f"{source} profile {name} {artifact_key} must be a string")
            else:
                errors.extend(
                    _artifact_path_errors(value, run_id, f"{source} profile {name}", artifact_key)
                )
        metrics = profile.get("metrics")
        if not isinstance(metrics, dict):
            errors.append(f"{source} profile {name} metrics must be an object")
            continue
        if metrics.get("solve_prompt_count") == 0 and metrics.get("e2e_solve_p95_ms", 0) > 0:
            errors.append(
                f"{source} profile {name} cannot claim E2E solve P95 with solve_prompt_count=0"
            )
        if metrics.get("completed_stream_count", 0) > metrics.get("request_count", 0):
            errors.append(f"{source} profile {name} completed_stream_count exceeds request_count")
        token_method = metrics.get("token_count_method")
        if token_method not in {"provider_usage", "content_unit_approximation"}:
            errors.append(f"{source} profile {name} has invalid token_count_method")
        for metric_key in metrics:
            if metric_key.endswith("_seconds"):
                errors.append(f"{source} profile {name} metric {metric_key} must use ms fields")
        if real_evidence and profiles_config is not None:
            profile_config = profiles_config.get(name)
            if isinstance(profile_config, dict):
                first_token_p50_max = profile_config.get("first_token_p50_max_ms")
                if (
                    isinstance(first_token_p50_max, int | float)
                    and metrics.get("first_token_p50_ms", 0) >= first_token_p50_max
                ):
                    errors.append(f"{source} profile {name} first_token_p50_ms fails threshold")
                first_token_p95_max = profile_config.get("first_token_p95_max_ms")
                if (
                    isinstance(first_token_p95_max, int | float)
                    and metrics.get("first_token_p95_ms", 0) >= first_token_p95_max
                ):
                    errors.append(f"{source} profile {name} first_token_p95_ms fails threshold")
                streaming_min = profile_config.get("streaming_min_tokens_per_second")
                if (
                    isinstance(streaming_min, int | float)
                    and metrics.get("streaming_tokens_per_second", 0) < streaming_min
                ):
                    errors.append(
                        f"{source} profile {name} streaming_tokens_per_second fails threshold"
                    )
                if (
                    isinstance(profile_config.get("oom_count_max"), int)
                    and metrics.get("oom_count", 0) > profile_config["oom_count_max"]
                ):
                    errors.append(f"{source} profile {name} oom_count fails threshold")
                if (
                    isinstance(profile_config.get("deadlock_count_max"), int)
                    and metrics.get("deadlock_count", 0) > profile_config["deadlock_count_max"]
                ):
                    errors.append(f"{source} profile {name} deadlock_count fails threshold")
        if real_evidence and hard_gate_config is not None:
            hard_first_token_p95 = hard_gate_config.get("first_token_p95_max_ms")
            if (
                isinstance(hard_first_token_p95, int | float)
                and metrics.get("first_token_p95_ms", 0) >= hard_first_token_p95
            ):
                errors.append(f"{source} profile {name} hard-gate first_token_p95_ms fails")
            hard_streaming_min = hard_gate_config.get("streaming_min_tokens_per_second")
            if (
                isinstance(hard_streaming_min, int | float)
                and metrics.get("streaming_tokens_per_second", 0) < hard_streaming_min
            ):
                errors.append(
                    f"{source} profile {name} hard-gate streaming_tokens_per_second fails"
                )
            hard_e2e_p95 = hard_gate_config.get("e2e_solve_p95_max_ms")
            if (
                isinstance(hard_e2e_p95, int | float)
                and metrics.get("e2e_solve_p95_ms", 0) > hard_e2e_p95
            ):
                errors.append(f"{source} profile {name} hard-gate e2e_solve_p95_ms fails")
    errors.extend(validate_no_secret_like_values(manifest, source))
    return errors


def validate_single_node_manifest(
    manifest: dict[str, Any],
    expected_hash: str,
    *,
    source: str,
    real_evidence: bool,
    profile_config: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str):
        return [f"{source} run_id must be a string"]
    if manifest.get("source_story") != "M3.6b":
        errors.append(f"{source} source_story must be M3.6b")
    if manifest.get("environment") != "single-node-dev":
        errors.append(f"{source} environment must be single-node-dev")
    if manifest.get("node_count") != 1:
        errors.append(f"{source} node_count must be 1")
    if manifest.get("prompt_fixture") != "tools/chat_load/prompts_v1.json":
        errors.append(f"{source} prompt_fixture must reference prompts_v1.json")
    if manifest.get("prompt_fixture_sha256") != expected_hash:
        errors.append(f"{source} prompt_fixture_sha256 does not match prompts_v1.json")
    if manifest.get("prompt_count") != 100:
        errors.append(f"{source} prompt_count must be 100")

    example_only = manifest.get("example_only")
    if real_evidence and example_only is not False:
        errors.append(f"{source} real single-node evidence must set example_only=false")
    if not real_evidence and example_only is not True:
        errors.append(f"{source} example single-node manifest must set example_only=true")

    for path, value in _walk_values(manifest):
        if path.endswith(".hard_gate_candidate") and value is not False:
            errors.append(f"{source} single-node evidence cannot be a hard-gate candidate")
        if path.endswith(".hard_gate_pass") and value:
            errors.append(f"{source} single-node evidence cannot claim hard-gate pass")

    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        return errors + [f"{source} profiles must be an object"]
    if set(profiles) != {SINGLE_NODE_PROFILE}:
        errors.append(f"{source} profiles must contain only single_node_baseline")

    profile = profiles.get(SINGLE_NODE_PROFILE)
    if not isinstance(profile, dict):
        return errors + [f"{source} single_node_baseline must be an object"]
    if profile.get("profile") != SINGLE_NODE_PROFILE:
        errors.append(f"{source} profile field must be single_node_baseline")
    for artifact_key in ("locust_report", "metrics_snapshot"):
        value = profile.get(artifact_key)
        if not isinstance(value, str):
            errors.append(f"{source} {artifact_key} must be a string")
        else:
            errors.extend(
                _single_node_artifact_path_errors(
                    value, run_id, f"{source} single_node_baseline", artifact_key
                )
            )
    metrics = profile.get("metrics")
    if not isinstance(metrics, dict):
        return errors + [f"{source} single_node_baseline metrics must be an object"]
    if metrics.get("solve_prompt_count") == 0 and metrics.get("e2e_solve_p95_ms", 0) > 0:
        errors.append(f"{source} cannot claim E2E solve P95 with solve_prompt_count=0")
    if metrics.get("completed_stream_count", 0) > metrics.get("request_count", 0):
        errors.append(f"{source} completed_stream_count exceeds request_count")
    token_method = metrics.get("token_count_method")
    if token_method not in {"provider_usage", "content_unit_approximation"}:
        errors.append(f"{source} has invalid token_count_method")
    for metric_key in metrics:
        if metric_key.endswith("_seconds"):
            errors.append(f"{source} metric {metric_key} must use ms fields")
    if real_evidence and profile_config is not None:
        threshold_pairs = {
            "first_token_p50_ms": "first_token_p50_max_ms",
            "first_token_p95_ms": "first_token_p95_max_ms",
            "e2e_solve_p95_ms": "e2e_solve_p95_max_ms",
            "sandbox_startup_p95_ms": "sandbox_startup_p95_max_ms",
            "capability_lookup_p95_ms": "capability_lookup_p95_max_ms",
            "chat_internal_hop_p95_ms": "chat_internal_hop_p95_max_ms",
        }
        for metric_key, threshold_key in threshold_pairs.items():
            threshold = profile_config.get(threshold_key)
            if (
                isinstance(threshold, int | float)
                and isinstance(metrics.get(metric_key), int | float)
                and metrics[metric_key] >= threshold
            ):
                errors.append(f"{source} {metric_key} fails advisory threshold")
        streaming_min = profile_config.get("streaming_min_tokens_per_second")
        if (
            isinstance(streaming_min, int | float)
            and isinstance(metrics.get("streaming_tokens_per_second"), int | float)
            and metrics["streaming_tokens_per_second"] < streaming_min
        ):
            errors.append(f"{source} streaming_tokens_per_second fails advisory threshold")

    errors.extend(validate_no_secret_like_values(manifest, source))
    return errors


def validate_incident_fallback_manifest(
    manifest: dict[str, Any],
    expected_hash: str,
    plan_hash: str,
    *,
    source: str,
    real_evidence: bool,
    plan_config: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str):
        return [f"{source} run_id must be a string"]
    if manifest.get("source_story") != "M3.6c":
        errors.append(f"{source} source_story must be M3.6c")
    if manifest.get("environment") != "staging-incident-drill":
        errors.append(f"{source} environment must be staging-incident-drill")
    if manifest.get("primary_provider") != "deepseek-v3.5":
        errors.append(f"{source} primary_provider must be deepseek-v3.5")
    if manifest.get("fallback_provider") != "qwen-max":
        errors.append(f"{source} fallback_provider must be qwen-max")
    if manifest.get("prompt_fixture") != "tools/chat_load/prompts_v1.json":
        errors.append(f"{source} prompt_fixture must reference prompts_v1.json")
    if manifest.get("prompt_fixture_sha256") != expected_hash:
        errors.append(f"{source} prompt_fixture_sha256 does not match prompts_v1.json")
    if manifest.get("prompt_count") != 100:
        errors.append(f"{source} prompt_count must be 100")
    if manifest.get("drill_plan_sha256") != plan_hash:
        errors.append(f"{source} drill_plan_sha256 does not match incident fallback plan")

    example_only = manifest.get("example_only")
    if real_evidence and example_only is not False:
        errors.append(f"{source} real incident fallback evidence must set example_only=false")
    if not real_evidence and example_only is not True:
        errors.append(f"{source} example incident fallback manifest must set example_only=true")

    for path, value in _walk_values(manifest):
        if (
            path.endswith(".hard_gate_candidate")
            or path.endswith(".hard_gate_pass")
            or path.endswith(".staging_pass")
        ) and value:
            errors.append(
                f"{source} incident fallback evidence cannot claim hard-gate or staging pass"
            )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append(f"{source} artifacts must be an object")
    else:
        if set(artifacts) != INCIDENT_FALLBACK_ARTIFACTS:
            errors.append(f"{source} artifact fields drifted")
        for artifact_key in sorted(INCIDENT_FALLBACK_ARTIFACTS & set(artifacts)):
            value = artifacts.get(artifact_key)
            if not isinstance(value, str):
                errors.append(f"{source} {artifact_key} must be a string")
            else:
                errors.extend(
                    _incident_fallback_artifact_path_errors(
                        value, run_id, f"{source} {artifact_key}", artifact_key
                    )
                )

    timeline = manifest.get("timeline")
    if not isinstance(timeline, dict):
        errors.append(f"{source} timeline must be an object")
    else:
        if set(timeline) != INCIDENT_FALLBACK_TIMELINE_FIELDS:
            errors.append(f"{source} timeline fields drifted")
        operator_decision = _parse_utc_timestamp(timeline.get("operator_decision_utc"))
        fallback_confirmed = _parse_utc_timestamp(timeline.get("fallback_confirmed_utc"))
        measurement_started = _parse_utc_timestamp(timeline.get("measurement_started_utc"))
        measurement_ended = _parse_utc_timestamp(timeline.get("measurement_ended_utc"))
        incident_started = _parse_utc_timestamp(timeline.get("incident_started_utc"))
        provider_health_failed = _parse_utc_timestamp(timeline.get("provider_health_failed_utc"))
        if operator_decision is None or fallback_confirmed is None:
            errors.append(
                f"{source} operator_decision_utc and fallback_confirmed_utc must be valid"
            )
        elif fallback_confirmed <= operator_decision:
            errors.append(f"{source} fallback_confirmed_utc must be after operator_decision_utc")
        elif isinstance(manifest.get("metrics"), dict):
            expected_switch_seconds = (fallback_confirmed - operator_decision).total_seconds()
            if manifest["metrics"].get("switch_duration_seconds") != expected_switch_seconds:
                errors.append(f"{source} switch_duration_seconds must match timeline")
        if measurement_started is None or measurement_ended is None:
            errors.append(f"{source} measurement timestamps must be valid")
        elif measurement_ended <= measurement_started:
            errors.append(f"{source} measurement_ended_utc must be after measurement_started_utc")
        if incident_started is None or provider_health_failed is None:
            errors.append(f"{source} provider health detection timestamps must be valid")
        elif provider_health_failed < incident_started:
            errors.append(
                f"{source} provider_health_failed_utc must not precede incident_started_utc"
            )
        elif isinstance(manifest.get("metrics"), dict):
            expected_detection_seconds = (provider_health_failed - incident_started).total_seconds()
            if manifest["metrics"].get("detection_window_seconds") != expected_detection_seconds:
                errors.append(f"{source} detection_window_seconds must match timeline")

    metrics = manifest.get("metrics")
    if not isinstance(metrics, dict):
        return errors + [f"{source} metrics must be an object"]
    if set(metrics) != INCIDENT_FALLBACK_METRICS:
        errors.append(f"{source} metric fields drifted")
    if metrics.get("completed_stream_count", 0) > metrics.get("request_count", 0):
        errors.append(f"{source} completed_stream_count exceeds request_count")
    if metrics.get("schema_parity_total_count", 0) == 0:
        errors.append(f"{source} schema_parity_total_count must be greater than 0")
    if metrics.get("schema_parity_pass_count") != metrics.get("schema_parity_total_count"):
        errors.append(f"{source} schema parity counts must match")
    for metric_key in metrics:
        if metric_key.endswith("_seconds"):
            continue
        if "latency" in metric_key and not metric_key.endswith("_ms"):
            errors.append(f"{source} metric {metric_key} must use ms fields")
    if real_evidence and plan_config is not None:
        switch_budget = plan_config.get("switch_budget_seconds")
        if (
            isinstance(switch_budget, int | float)
            and isinstance(metrics.get("switch_duration_seconds"), int | float)
            and metrics["switch_duration_seconds"] > switch_budget
        ):
            errors.append(f"{source} switch_duration_seconds fails threshold")
        fallback_p95_max = plan_config.get("fallback_first_token_p95_max_ms")
        if (
            isinstance(fallback_p95_max, int | float)
            and isinstance(metrics.get("fallback_first_token_p95_ms"), int | float)
            and metrics["fallback_first_token_p95_ms"] >= fallback_p95_max
        ):
            errors.append(f"{source} fallback_first_token_p95_ms fails threshold")
        route_ratio_min = plan_config.get("fallback_route_ratio_min")
        if (
            isinstance(route_ratio_min, int | float)
            and isinstance(metrics.get("fallback_route_ratio"), int | float)
            and metrics["fallback_route_ratio"] < route_ratio_min
        ):
            errors.append(f"{source} fallback_route_ratio fails threshold")
        if metrics.get("fallback_provider_error_count", 0) > 0:
            errors.append(f"{source} fallback_provider_error_count must be 0")

    errors.extend(validate_no_secret_like_values(manifest, source))
    return errors


def validate_all(
    evidence_path: Path | None = None,
    single_node_evidence_path: Path | None = None,
    incident_fallback_evidence_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    prompts = load_json(PROMPTS_PATH)
    profiles = load_json(PROFILES_PATH)
    schema = load_json(SCHEMA_PATH)
    example_manifest = load_json(EXAMPLE_MANIFEST_PATH)
    single_node_profiles = load_json(SINGLE_NODE_PROFILES_PATH)
    single_node_schema = load_json(SINGLE_NODE_SCHEMA_PATH)
    single_node_example_manifest = load_json(SINGLE_NODE_EXAMPLE_MANIFEST_PATH)
    incident_fallback_plan = load_json(INCIDENT_FALLBACK_PLAN_PATH)
    incident_fallback_schema = load_json(INCIDENT_FALLBACK_SCHEMA_PATH)
    incident_fallback_example_manifest = load_json(INCIDENT_FALLBACK_EXAMPLE_MANIFEST_PATH)
    if not isinstance(prompts, dict):
        return ["prompts_v1.json must contain an object"]
    expected_hash = prompt_fixture_hash(prompts)
    incident_plan_hash = canonical_sha256(incident_fallback_plan)
    profiles_config = profiles.get("profiles") if isinstance(profiles, dict) else None
    hard_gate_config = profiles.get("hard_gate_thresholds") if isinstance(profiles, dict) else None
    errors.extend(validate_prompts(prompts))
    if not isinstance(profiles, dict):
        errors.append("staging_profiles.json must contain an object")
    else:
        errors.extend(validate_profiles(profiles, expected_hash))
    if not isinstance(single_node_profiles, dict):
        errors.append("single_node_profiles.json must contain an object")
    else:
        errors.extend(validate_single_node_profiles(single_node_profiles, expected_hash))
    if not isinstance(incident_fallback_plan, dict):
        errors.append("incident_fallback_plan.json must contain an object")
    else:
        errors.extend(validate_incident_fallback_plan(incident_fallback_plan, expected_hash))
    if not isinstance(schema, dict):
        errors.append("evidence_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_schema(schema))
    if not isinstance(single_node_schema, dict):
        errors.append("single_node_evidence_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_single_node_schema(single_node_schema))
    if not isinstance(incident_fallback_schema, dict):
        errors.append("incident_fallback_evidence_manifest.schema.json must contain an object")
    else:
        errors.extend(validate_incident_fallback_schema(incident_fallback_schema))
    if not isinstance(example_manifest, dict):
        errors.append("evidence_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_manifest(
                example_manifest,
                expected_hash,
                source="evidence_manifest.example.json",
                real_evidence=False,
            )
        )
    if not isinstance(single_node_example_manifest, dict):
        errors.append("single_node_evidence_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_single_node_manifest(
                single_node_example_manifest,
                expected_hash,
                source="single_node_evidence_manifest.example.json",
                real_evidence=False,
            )
        )
    if not isinstance(incident_fallback_example_manifest, dict):
        errors.append("incident_fallback_evidence_manifest.example.json must contain an object")
    else:
        errors.extend(
            validate_incident_fallback_manifest(
                incident_fallback_example_manifest,
                expected_hash,
                incident_plan_hash,
                source="incident_fallback_evidence_manifest.example.json",
                real_evidence=False,
            )
        )
    errors.extend(validate_locustfile())
    errors.extend(validate_single_node_locustfile())

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
            errors.extend(validate_evidence_path_mode(Path(relative), "staging"))
            errors.extend(
                validate_manifest(
                    evidence,
                    expected_hash,
                    source=relative,
                    real_evidence=True,
                    profiles_config=profiles_config if isinstance(profiles_config, dict) else None,
                    hard_gate_config=hard_gate_config
                    if isinstance(hard_gate_config, dict)
                    else None,
                )
            )
    if single_node_evidence_path is not None:
        evidence = load_json(single_node_evidence_path)
        if not isinstance(evidence, dict):
            errors.append(f"{single_node_evidence_path} must contain an object")
        else:
            try:
                relative = (
                    single_node_evidence_path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
                )
            except ValueError:
                relative = single_node_evidence_path.as_posix()
                errors.append("--single-node-evidence path must be inside the repository")
            errors.extend(validate_evidence_path_mode(Path(relative), "single-node"))
            single_node_profiles_config = (
                single_node_profiles.get("profiles", {})
                if isinstance(single_node_profiles, dict)
                else {}
            )
            profile_config = (
                single_node_profiles_config.get(SINGLE_NODE_PROFILE)
                if isinstance(single_node_profiles_config, dict)
                else None
            )
            errors.extend(
                validate_single_node_manifest(
                    evidence,
                    expected_hash,
                    source=relative,
                    real_evidence=True,
                    profile_config=profile_config if isinstance(profile_config, dict) else None,
                )
            )
    if incident_fallback_evidence_path is not None:
        evidence = load_json(incident_fallback_evidence_path)
        if not isinstance(evidence, dict):
            errors.append(f"{incident_fallback_evidence_path} must contain an object")
        else:
            try:
                relative = (
                    incident_fallback_evidence_path.resolve()
                    .relative_to(REPO_ROOT.resolve())
                    .as_posix()
                )
            except ValueError:
                relative = incident_fallback_evidence_path.as_posix()
                errors.append("--incident-fallback-evidence path must be inside the repository")
            errors.extend(validate_evidence_path_mode(Path(relative), "incident-fallback"))
            errors.extend(
                validate_incident_fallback_manifest(
                    evidence,
                    expected_hash,
                    incident_plan_hash,
                    source=relative,
                    real_evidence=True,
                    plan_config=incident_fallback_plan
                    if isinstance(incident_fallback_plan, dict)
                    else None,
                )
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Optional real operator evidence manifest under reports/chat-load/<run_id>/",
    )
    parser.add_argument(
        "--single-node-evidence",
        type=Path,
        help="Optional real single-node evidence manifest under reports/chat-single-node/<run_id>/",
    )
    parser.add_argument(
        "--incident-fallback-evidence",
        type=Path,
        help=(
            "Optional real incident fallback evidence manifest under "
            "reports/chat-incident-fallback/<run_id>/"
        ),
    )
    args = parser.parse_args(argv)

    errors = validate_all(
        args.evidence,
        args.single_node_evidence,
        args.incident_fallback_evidence,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("chat load plan OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
