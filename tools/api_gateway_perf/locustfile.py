"""Locust harness for M3.6d API gateway performance baseline.

CI imports this module for helper validation without requiring Locust. Real
operators run it with Locust against the staging API gateway.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:  # pragma: no cover - CI does not need the Locust runtime.
    from locust import HttpUser, constant_pacing, task
except ImportError:  # pragma: no cover - exercised by static validation only.
    HttpUser = object  # type: ignore[assignment,misc]

    def constant_pacing(seconds: float) -> float:
        return seconds

    def task(func: Any) -> Any:
        return func


REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = REPO_ROOT / "tools" / "api_gateway_perf" / "perf_baseline_plan.json"
DEFAULT_ENDPOINT_CLASSES = ("algorithms_public", "auth_api_keys", "business_demo")
AUTH_ENV_VAR = "API_GATEWAY_PERF_JWT"

DEMO_LP_PAYLOAD: dict[str, Any] = {
    "task_type": "lp",
    "objective": {"sense": "min", "coefficients": {"x": 1, "y": 2}},
    "constraints": [
        {"name": "capacity", "coefficients": {"x": 1, "y": 1}, "sense": "<=", "rhs": 4}
    ],
    "bounds": {"x": {"lower": 0}, "y": {"lower": 0}},
    "options": {"max_solve_seconds": 5},
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def load_plan(path: Path = PLAN_PATH) -> dict[str, Any]:
    data = load_json(path)
    endpoints = data.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError("perf_baseline_plan.json must contain endpoint definitions")
    return data


def endpoint_classes_from_env(environ: dict[str, str] | None = None) -> list[str]:
    source = environ if environ is not None else os.environ
    raw = source.get("API_GATEWAY_PERF_ENDPOINT_CLASSES")
    if raw is None or not raw.strip():
        return list(DEFAULT_ENDPOINT_CLASSES)
    selected = [value.strip() for value in raw.split(",") if value.strip()]
    unknown = sorted(set(selected) - set(DEFAULT_ENDPOINT_CLASSES))
    if unknown:
        raise ValueError(f"unknown API gateway endpoint classes: {', '.join(unknown)}")
    return selected


def selected_endpoints(
    plan: dict[str, Any] | None = None,
    environ: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    loaded_plan = plan if plan is not None else load_plan()
    endpoint_classes = endpoint_classes_from_env(environ)
    endpoints = loaded_plan.get("endpoints")
    if not isinstance(endpoints, list):
        raise ValueError("plan endpoints must be a list")
    by_class = {
        endpoint["endpoint_class"]: endpoint
        for endpoint in endpoints
        if isinstance(endpoint, dict) and isinstance(endpoint.get("endpoint_class"), str)
    }
    return [by_class[name] for name in endpoint_classes]


def request_interval_seconds(plan: dict[str, Any] | None = None) -> float:
    loaded_plan = plan if plan is not None else load_plan()
    profile = loaded_plan.get("profile")
    endpoints = loaded_plan.get("endpoints")
    if not isinstance(profile, dict) or not isinstance(endpoints, list):
        raise ValueError("plan must contain profile and endpoints")
    users = float(profile["users"])
    total_weight = sum(float(endpoint.get("weight", 1)) for endpoint in endpoints)
    if users <= 0 or total_weight <= 0:
        raise ValueError("users and endpoint weights must be positive")
    return max(users / total_weight, 0.001)


def build_request_spec(
    endpoint: dict[str, Any],
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    source = environ if environ is not None else os.environ
    endpoint_class = endpoint.get("endpoint_class")
    method = endpoint.get("method")
    path = endpoint.get("path")
    auth_mode = endpoint.get("auth_mode")
    if not isinstance(endpoint_class, str):
        raise ValueError("endpoint_class must be a string")
    if method not in {"GET", "POST"}:
        raise ValueError(f"unsupported method for {endpoint_class}: {method}")
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError(f"path must start with / for {endpoint_class}")

    headers: dict[str, str] = {}
    json_body: dict[str, Any] | None = None
    if auth_mode == "jwt_bearer_env":
        token = source.get(AUTH_ENV_VAR, "").strip()
        if not token:
            raise ValueError(f"{AUTH_ENV_VAR} is required for {endpoint_class}")
        headers["Authorization"] = f"Bearer {token}"
    elif auth_mode != "none":
        raise ValueError(f"unsupported auth_mode for {endpoint_class}: {auth_mode}")

    if method == "POST" and endpoint_class == "business_demo":
        json_body = DEMO_LP_PAYLOAD
    return {
        "endpoint_class": endpoint_class,
        "method": method,
        "path": path,
        "headers": headers,
        "json": json_body,
    }


class ApiGatewayPerfUser(HttpUser):  # type: ignore[misc]
    """Locust user for API gateway baseline requests."""

    plan = load_plan()
    wait_time = constant_pacing(request_interval_seconds(plan))
    _endpoint_index = 0

    @task
    def gateway_request(self) -> None:
        endpoints = selected_endpoints(self.plan)
        endpoint = endpoints[self._endpoint_index % len(endpoints)]
        self._endpoint_index += 1
        spec = build_request_spec(endpoint)
        request_name = f"api_gateway/{spec['endpoint_class']}"
        if spec["method"] == "GET":
            self.client.get(  # type: ignore[attr-defined]
                spec["path"],
                headers=spec["headers"],
                name=request_name,
            )
        else:
            self.client.post(  # type: ignore[attr-defined]
                spec["path"],
                json=spec["json"],
                headers=spec["headers"],
                name=request_name,
            )
