"""Validate M3.6a Chat staging load-test plan assets.

The validator is static by default. It validates real operator evidence only
when an explicit evidence manifest is passed with --evidence.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
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
REQUIRED_PROFILES = {"baseline", "stress", "soak"}
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


def prompt_fixture_hash(data: dict[str, Any]) -> str:
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


def validate_all(evidence_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    prompts = load_json(PROMPTS_PATH)
    profiles = load_json(PROFILES_PATH)
    schema = load_json(SCHEMA_PATH)
    example_manifest = load_json(EXAMPLE_MANIFEST_PATH)
    if not isinstance(prompts, dict):
        return ["prompts_v1.json must contain an object"]
    expected_hash = prompt_fixture_hash(prompts)
    profiles_config = profiles.get("profiles") if isinstance(profiles, dict) else None
    hard_gate_config = profiles.get("hard_gate_thresholds") if isinstance(profiles, dict) else None
    errors.extend(validate_prompts(prompts))
    if not isinstance(profiles, dict):
        errors.append("staging_profiles.json must contain an object")
    else:
        errors.extend(validate_profiles(profiles, expected_hash))
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
                expected_hash,
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
            if not relative.startswith("reports/chat-load/") or not relative.endswith(
                "/evidence_manifest.json"
            ):
                errors.append(
                    "--evidence path must be reports/chat-load/<run_id>/evidence_manifest.json"
                )
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
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Optional real operator evidence manifest under reports/chat-load/<run_id>/",
    )
    args = parser.parse_args(argv)

    errors = validate_all(args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("chat load plan OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
