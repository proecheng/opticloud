"""Locust harness for M3.6a Chat staging latency tests.

CI imports this module for helper validation without requiring Locust. Real
operators run it with Locust against a 5-node staging cluster.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from hashlib import sha256
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
PROMPTS_PATH = REPO_ROOT / "tools" / "chat_load" / "prompts_v1.json"
PROFILES_PATH = REPO_ROOT / "tools" / "chat_load" / "staging_profiles.json"
DEFAULT_ENDPOINT = "/v1/chat/stream"
KNOWN_PROFILES = {"baseline", "stress", "soak"}
TOKEN_METHOD_PROVIDER = "provider_usage"
TOKEN_METHOD_APPROXIMATION = "content_unit_approximation"


@dataclass(frozen=True)
class StreamMetrics:
    first_token_latency_ms: float | None
    total_response_latency_ms: float
    streaming_tokens_per_second: float
    token_count_method: str
    token_units: int
    completed: bool


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def prompt_fixture_sha256(path: Path = PROMPTS_PATH) -> str:
    return sha256(canonical_json_bytes(load_json(path))).hexdigest()


def load_profiles(path: Path = PROFILES_PATH) -> dict[str, Any]:
    data = load_json(path)
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("staging_profiles.json must contain a profiles object")
    if set(profiles) != KNOWN_PROFILES:
        raise ValueError("profiles must be exactly baseline, stress, and soak")
    return profiles


def selected_profile_name(environ: dict[str, str] | None = None) -> str:
    source = environ if environ is not None else os.environ
    profile = source.get("CHAT_LOAD_PROFILE", "baseline")
    if profile not in KNOWN_PROFILES:
        raise ValueError(f"unknown CHAT_LOAD_PROFILE: {profile}")
    return profile


def load_selected_profile(environ: dict[str, str] | None = None) -> dict[str, Any]:
    profiles = load_profiles()
    return profiles[selected_profile_name(environ)]


def request_interval_seconds(profile: dict[str, Any]) -> float:
    per_minute = float(profile["effective_requests_per_user_per_minute"])
    if per_minute <= 0:
        raise ValueError("effective_requests_per_user_per_minute must be positive")
    return 60.0 / per_minute


def chat_endpoint(environ: dict[str, str] | None = None) -> str:
    source = environ if environ is not None else os.environ
    endpoint = source.get("CHAT_LOAD_ENDPOINT", DEFAULT_ENDPOINT)
    if not endpoint.startswith("/"):
        raise ValueError("CHAT_LOAD_ENDPOINT must be a path beginning with /")
    return endpoint


def iter_sse_data_lines(chunks: Iterable[bytes | str]) -> Iterator[str]:
    buffer = ""
    for chunk in chunks:
        text = chunk.decode("utf-8", errors="replace") if isinstance(chunk, bytes) else chunk
        buffer += text
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if line.startswith("data:"):
                data = line[5:].strip()
                if data:
                    yield data
    trailing = buffer.strip()
    if trailing.startswith("data:"):
        data = trailing[5:].strip()
        if data:
            yield data


def _json_payload(data: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def extract_token_units(data: str) -> tuple[int, str]:
    payload = _json_payload(data)
    if payload is None:
        stripped = data.strip()
        return (1 if stripped and stripped != "[DONE]" else 0, TOKEN_METHOD_APPROXIMATION)

    usage = payload.get("usage")
    if isinstance(usage, dict):
        for key in ("completion_tokens", "output_tokens", "tokens"):
            value = usage.get(key)
            if isinstance(value, int) and value > 0:
                return value, TOKEN_METHOD_PROVIDER

    candidates: list[str] = []
    for key in ("content", "token", "text"):
        value = payload.get(key)
        if isinstance(value, str):
            candidates.append(value)
    delta = payload.get("delta")
    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
        candidates.append(delta["content"])

    unit_count = sum(max(1, len(value.strip().split())) for value in candidates if value.strip())
    return unit_count, TOKEN_METHOD_APPROXIMATION


def calculate_stream_metrics(
    started_at: float,
    completed_at: float,
    events: Iterable[tuple[float, str]],
) -> StreamMetrics:
    first_token_at: float | None = None
    token_units = 0
    used_provider_usage = False

    for event_at, data in events:
        units, method = extract_token_units(data)
        if units <= 0:
            continue
        if first_token_at is None:
            first_token_at = event_at
        token_units += units
        used_provider_usage = used_provider_usage or method == TOKEN_METHOD_PROVIDER

    if first_token_at is None:
        return StreamMetrics(
            first_token_latency_ms=None,
            total_response_latency_ms=(completed_at - started_at) * 1000,
            streaming_tokens_per_second=0.0,
            token_count_method=TOKEN_METHOD_APPROXIMATION,
            token_units=0,
            completed=False,
        )

    streaming_seconds = max(completed_at - first_token_at, 0.001)
    method = TOKEN_METHOD_PROVIDER if used_provider_usage else TOKEN_METHOD_APPROXIMATION
    return StreamMetrics(
        first_token_latency_ms=(first_token_at - started_at) * 1000,
        total_response_latency_ms=(completed_at - started_at) * 1000,
        streaming_tokens_per_second=token_units / streaming_seconds,
        token_count_method=method,
        token_units=token_units,
        completed=True,
    )


def next_prompt(index: int, path: Path = PROMPTS_PATH) -> dict[str, Any]:
    data = load_json(path)
    prompts = data.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("prompts_v1.json must contain non-empty prompts")
    prompt = prompts[index % len(prompts)]
    if not isinstance(prompt, dict):
        raise ValueError("prompt record must be an object")
    return prompt


class ChatLoadUser(HttpUser):  # type: ignore[misc]
    """Locust user for staging Chat SSE load.

    This class is intentionally thin; validation logic lives in pure helpers.
    """

    profile = load_selected_profile()
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
            },
        }

        with self.client.post(  # type: ignore[attr-defined]
            chat_endpoint(),
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
                    f"chat stream failed status={response.status_code} completed={metrics.completed}"
                )
            else:
                response.success()
