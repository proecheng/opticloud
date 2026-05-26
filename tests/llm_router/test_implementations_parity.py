from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages" / "shared-py"))

from opticloud_shared.llm_router import (  # noqa: E402
    Completion,
    DeepSeekCompatibleProvider,
    LLMRouter,
    LLMRouterError,
    MockLLMProvider,
    Prompt,
    PromptMessage,
    QwenCompatibleProvider,
    build_default_router,
    complete,
)
from opticloud_shared.llm_router.parity import (  # noqa: E402
    PARITY_THRESHOLD,
    compute_behavior_parity_report,
    cosine_similarity,
    token_vector,
)
from opticloud_shared.llm_router.registry import (  # noqa: E402
    CANONICAL_IMPLEMENTATION_IDS,
    CANONICAL_MODEL_ALIASES,
    CANONICAL_PROVIDER_IDS,
    default_model_registry,
    default_provider_configs,
)

REFERENCE_PROMPTS_PATH = REPO_ROOT / "tools" / "llm_router" / "reference_prompts_v1.json"
PARITY_REPORT_PATH = REPO_ROOT / "tools" / "llm_router" / "parity_report.example.json"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_llm_router_contract.py"


def _sample_prompt(prompt_id: str = "llm-router-ref-test") -> Prompt:
    return Prompt(
        prompt_id=prompt_id,
        task="router_intent",
        locale="zh-CN",
        messages=[
            PromptMessage(role="system", content="Return a compact routing decision."),
            PromptMessage(role="user", content="请判断这是 VRPTW 还是库存优化任务。"),
        ],
        response_schema={
            "type": "object",
            "properties": {
                "task_type": {"type": "string"},
                "confidence": {"type": "number"},
                "reasoning": {"type": "string"},
            },
        },
    )


def test_prompt_and_completion_schema_reject_unsafe_drift() -> None:
    prompt = _sample_prompt()
    assert prompt.messages[0].role == "system"

    with pytest.raises(ValidationError):
        Prompt(
            prompt_id="bad",
            task="router_intent",
            messages=[PromptMessage(role="user", content="")],
        )

    with pytest.raises(ValidationError):
        Prompt(
            prompt_id="bad",
            task="router_intent",
            messages=[{"role": "developer", "content": "unsupported"}],
        )

    with pytest.raises(ValidationError):
        Prompt(
            prompt_id="bad",
            task="router_intent",
            messages=[PromptMessage(role="user", content="hello")],
            metadata={"api_key": "sk-live-secret"},
        )

    with pytest.raises(ValidationError):
        Completion(
            text="ok",
            model="deepseek-v3.5",
            provider="deepseek-compatible",
            finish_reason="stop",
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 3},
        )

    with pytest.raises(ValidationError):
        Completion(
            text="ok",
            model="deepseek-v3.5",
            provider="deepseek-compatible",
            finish_reason="stop",
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            raw_response_redacted={"choices": [{"message": {"content": "raw payload"}}]},
        )


def test_default_registry_has_canonical_aliases_and_providers() -> None:
    providers = default_provider_configs()
    registry = default_model_registry()

    assert tuple(providers) == CANONICAL_PROVIDER_IDS
    assert (
        tuple(item.implementation_id for item in providers.values()) == CANONICAL_IMPLEMENTATION_IDS
    )
    assert tuple(registry) == CANONICAL_MODEL_ALIASES
    assert registry["deepseek-v3.5"].provider_id == "deepseek-compatible"
    assert registry["qwen-max"].provider_id == "qwen-compatible"
    assert registry["mock-deterministic"].provider_id == "mock"
    assert registry["qwen-max"].is_fallback_eligible is True
    assert registry["mock-deterministic"].is_fallback_eligible is False


def test_complete_returns_completion_and_unknown_alias_fails_closed() -> None:
    prompt = _sample_prompt()

    result = complete(prompt, model="deepseek-v3.5")

    assert isinstance(result, Completion)
    assert result.model == "deepseek-v3.5"
    assert result.provider == "deepseek-compatible"
    assert result.text

    with pytest.raises(LLMRouterError):
        complete(prompt, model="unknown-provider")


def test_all_three_providers_share_schema_contract() -> None:
    prompt = _sample_prompt()
    router = build_default_router()

    results = [
        router.complete(prompt, model="mock-deterministic"),
        router.complete(prompt, model="deepseek-v3.5"),
        router.complete(prompt, model="qwen-max"),
    ]

    assert {result.provider for result in results} == {
        "mock",
        "deepseek-compatible",
        "qwen-compatible",
    }
    assert all(isinstance(result, Completion) for result in results)
    assert all(
        result.usage.total_tokens == result.usage.prompt_tokens + result.usage.completion_tokens
        for result in results
    )
    assert all(set(result.model_dump()) == set(results[0].model_dump()) for result in results)


def test_openai_compatible_adapters_normalize_chat_and_completion_envelopes() -> None:
    prompt = _sample_prompt()

    deepseek = DeepSeekCompatibleProvider(
        transport=lambda _prompt, _config: {
            "choices": [{"message": {"content": "deepseek normalized"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
        }
    )
    qwen = QwenCompatibleProvider(
        transport=lambda _prompt, _config: {
            "choices": [{"text": "qwen normalized", "finish_reason": "length"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        }
    )
    registry = default_model_registry()

    deepseek_result = deepseek.complete(prompt, registry["deepseek-v3.5"])
    qwen_result = qwen.complete(prompt, registry["qwen-max"])

    assert deepseek_result.text == "deepseek normalized"
    assert deepseek_result.finish_reason == "stop"
    assert deepseek_result.usage.total_tokens == 14
    assert qwen_result.text == "qwen normalized"
    assert qwen_result.finish_reason == "length"
    assert qwen_result.usage.total_tokens == 12


def test_provider_errors_and_malformed_envelopes_are_redacted() -> None:
    prompt = _sample_prompt()
    registry = default_model_registry()

    provider = DeepSeekCompatibleProvider(
        transport=lambda _prompt, _config: (_ for _ in ()).throw(
            RuntimeError("api_key=sk-secret Authorization: Bearer live-token cookie=session")
        )
    )
    with pytest.raises(LLMRouterError) as error_info:
        provider.complete(prompt, registry["deepseek-v3.5"])
    error_text = str(error_info.value)
    assert "sk-secret" not in error_text
    assert "Bearer live-token" not in error_text
    assert "cookie=session" not in error_text

    malformed = QwenCompatibleProvider(transport=lambda _prompt, _config: {"choices": []})
    with pytest.raises(LLMRouterError):
        malformed.complete(prompt, registry["qwen-max"])


def test_incident_fallback_is_explicit_and_schema_compatible() -> None:
    prompt = _sample_prompt()

    normal_router = build_default_router()
    normal_result = normal_router.complete(prompt, model="deepseek-v3.5")
    assert normal_result.model == "deepseek-v3.5"
    assert normal_result.provider == "deepseek-compatible"

    incident_router = build_default_router(unavailable_aliases={"deepseek-v3.5"})
    fallback_result = incident_router.complete(prompt, model="deepseek-v3.5")

    assert fallback_result.model == "qwen-max"
    assert fallback_result.provider == "qwen-compatible"
    assert fallback_result.raw_response_redacted is not None
    assert fallback_result.raw_response_redacted["fallback_from"] == "deepseek-v3.5"
    assert fallback_result.raw_response_redacted["fallback_reason"] == "primary_unavailable"


def test_router_rejects_missing_provider_implementation() -> None:
    router = LLMRouter(
        providers={"mock": MockLLMProvider()},
        model_registry=default_model_registry(),
    )
    with pytest.raises(LLMRouterError):
        router.complete(_sample_prompt(), model="deepseek-v3.5")


def test_reference_prompt_fixture_has_exactly_100_stable_prompts() -> None:
    fixture = json.loads(REFERENCE_PROMPTS_PATH.read_text(encoding="utf-8"))
    prompts = fixture["prompts"]

    assert fixture["dataset_version"] == "llm_router_reference_prompts_v1"
    assert fixture["source_story"] == "M3.8"
    assert fixture["prompt_count"] == 100
    assert len(prompts) == 100
    assert [prompt["prompt_id"] for prompt in prompts] == [
        f"llm-router-ref-{index:03d}" for index in range(1, 101)
    ]
    counts: dict[str, int] = {}
    for prompt in prompts:
        counts[prompt["task"]] = counts.get(prompt["task"], 0) + 1
        Prompt.model_validate(prompt)
    assert counts == {
        "router_intent": 20,
        "formulator_extraction": 20,
        "coder_generation": 20,
        "critic_validation": 20,
        "mixed_language_summary": 20,
    }


def test_behavior_parity_report_passes_threshold_for_each_prompt() -> None:
    report = compute_behavior_parity_report(REFERENCE_PROMPTS_PATH)

    assert report["report_version"] == "llm_router_behavior_parity_v1"
    assert report["source_story"] == "M3.8"
    assert report["example_only"] is True
    assert report["primary_alias"] == "deepseek-v3.5"
    assert report["fallback_alias"] == "qwen-max"
    assert report["prompt_count"] == 100
    assert report["threshold"] == PARITY_THRESHOLD
    assert report["minimum_similarity"] >= PARITY_THRESHOLD
    assert report["passed"] is True
    assert len(report["deviations"]) == 100
    assert all(item["similarity"] >= PARITY_THRESHOLD for item in report["deviations"])
    assert len({item["primary_summary"] for item in report["deviations"]}) > 90
    assert len({item["fallback_summary"] for item in report["deviations"]}) > 90


def test_committed_parity_report_matches_computed_report() -> None:
    committed = json.loads(PARITY_REPORT_PATH.read_text(encoding="utf-8"))
    computed = compute_behavior_parity_report(REFERENCE_PROMPTS_PATH)

    assert committed == computed


def test_cosine_similarity_rejects_below_threshold_output() -> None:
    high = cosine_similarity(
        token_vector("router task_type vrptw confidence reasoning"),
        token_vector("router task_type vrptw confidence reasoning"),
    )
    low = cosine_similarity(
        token_vector("router task_type vrptw confidence reasoning"),
        token_vector("invoice payment refund unrelated"),
    )

    assert high == pytest.approx(1.0)
    assert low < PARITY_THRESHOLD


def test_validator_success_and_negative_drift_cases(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    fixture = json.loads(REFERENCE_PROMPTS_PATH.read_text(encoding="utf-8"))
    bad_fixture = copy.deepcopy(fixture)
    bad_fixture["prompts"] = bad_fixture["prompts"][:-1]
    bad_fixture["prompt_count"] = 99
    bad_fixture_path = tmp_path / "bad_prompts.json"
    bad_fixture_path.write_text(json.dumps(bad_fixture, ensure_ascii=False), encoding="utf-8")

    report = compute_behavior_parity_report(REFERENCE_PROMPTS_PATH)
    bad_report = copy.deepcopy(report)
    bad_report["example_only"] = False
    bad_report["evidence_type"] = "live provider evaluation"
    bad_report_path = tmp_path / "bad_report.json"
    bad_report_path.write_text(json.dumps(bad_report, ensure_ascii=False), encoding="utf-8")

    failed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "--reference-prompts",
            str(bad_fixture_path),
            "--parity-report",
            str(bad_report_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert failed.returncode != 0
    assert "expected exactly 100 reference prompts" in failed.stderr


def test_validator_rejects_below_threshold_and_global_canned_output(tmp_path: Path) -> None:
    report = compute_behavior_parity_report(REFERENCE_PROMPTS_PATH)
    bad_report = copy.deepcopy(report)
    bad_report["minimum_similarity"] = 0.1
    bad_report["passed"] = True
    for deviation in bad_report["deviations"]:
        deviation["similarity"] = 0.1
        deviation["primary_summary"] = "identical canned output"
        deviation["fallback_summary"] = "identical canned output"
    bad_report_path = tmp_path / "bad_report.json"
    bad_report_path.write_text(json.dumps(bad_report, ensure_ascii=False), encoding="utf-8")

    failed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "--parity-report",
            str(bad_report_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert failed.returncode != 0
    assert "below behavior parity threshold" in failed.stderr
