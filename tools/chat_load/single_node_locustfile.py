"""Locust harness for M3.6b Chat single-node baseline tests.

CI imports this module for helper validation without requiring Locust. Real
operators run it with Locust against a single-node local/dev Chat stack.
"""

from __future__ import annotations

import os
import time
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


from tools.chat_load.locustfile import (  # noqa: E402
    DEFAULT_ENDPOINT,
    REPO_ROOT,
    calculate_stream_metrics,
    chat_endpoint,
    iter_sse_data_lines,
    load_json,
    next_prompt,
    prompt_fixture_sha256,
    request_interval_seconds,
)

SINGLE_NODE_PROFILES_PATH = REPO_ROOT / "tools" / "chat_load" / "single_node_profiles.json"
SINGLE_NODE_PROFILE = "single_node_baseline"


def load_single_node_profiles(path: Path = SINGLE_NODE_PROFILES_PATH) -> dict[str, Any]:
    data = load_json(path)
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("single_node_profiles.json must contain a profiles object")
    if set(profiles) != {SINGLE_NODE_PROFILE}:
        raise ValueError("single-node profiles must contain only single_node_baseline")
    return profiles


def selected_single_node_profile_name(environ: dict[str, str] | None = None) -> str:
    source = environ if environ is not None else os.environ
    profile = source.get("CHAT_SINGLE_NODE_PROFILE", SINGLE_NODE_PROFILE)
    if profile != SINGLE_NODE_PROFILE:
        raise ValueError(f"unknown CHAT_SINGLE_NODE_PROFILE: {profile}")
    return profile


def load_selected_single_node_profile(environ: dict[str, str] | None = None) -> dict[str, Any]:
    profiles = load_single_node_profiles()
    return profiles[selected_single_node_profile_name(environ)]


def single_node_endpoint(environ: dict[str, str] | None = None) -> str:
    source = environ if environ is not None else os.environ
    return chat_endpoint({"CHAT_LOAD_ENDPOINT": source.get("CHAT_LOAD_ENDPOINT", DEFAULT_ENDPOINT)})


class ChatSingleNodeLoadUser(HttpUser):  # type: ignore[misc]
    """Locust user for single-node Chat SSE baseline runs."""

    profile = load_selected_single_node_profile()
    wait_time = constant_pacing(request_interval_seconds(profile))
    _prompt_index = 0

    @task
    def stream_chat(self) -> None:
        prompt = next_prompt(self._prompt_index)
        self._prompt_index += 1
        started_at = time.perf_counter()
        event_records: list[tuple[float, str]] = []
        payload = {
            "prompt": prompt["prompt"],
            "metadata": {
                "prompt_id": prompt["id"],
                "category": prompt["category"],
                "expected_path": prompt["expected_path"],
                "profile": SINGLE_NODE_PROFILE,
            },
        }

        with self.client.post(  # type: ignore[attr-defined]
            single_node_endpoint(),
            json=payload,
            stream=True,
            name=f"chat_stream/{self.profile['name']}",
            catch_response=True,
        ) as response:
            for data in iter_sse_data_lines(response.iter_content(chunk_size=None)):
                event_records.append((time.perf_counter(), data))
            completed_at = time.perf_counter()
            metrics = calculate_stream_metrics(started_at, completed_at, event_records)
            if response.status_code >= 400 or not metrics.completed:
                response.failure(
                    f"single-node chat stream failed status={response.status_code} "
                    f"completed={metrics.completed}"
                )
            else:
                response.success()


__all__ = [
    "DEFAULT_ENDPOINT",
    "SINGLE_NODE_PROFILE",
    "calculate_stream_metrics",
    "load_selected_single_node_profile",
    "load_single_node_profiles",
    "prompt_fixture_sha256",
    "request_interval_seconds",
    "selected_single_node_profile_name",
    "single_node_endpoint",
]
