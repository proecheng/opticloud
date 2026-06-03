from __future__ import annotations

import base64
import json

import pytest

from tests.aigc.datasets import BENIGN_PROMPTS, RED_TEAM_PROMPTS

_ZERO_WIDTH_START = "\u200b"
_ZERO_WIDTH_ZERO = "\u200c"
_ZERO_WIDTH_ONE = "\u200d"
_ZERO_WIDTH_END = "\u2060"


def _module_payload(metadata: dict[str, object]) -> str:
    raw = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    bits = "".join(f"{ord(char):08b}" for char in encoded)
    payload = "".join(_ZERO_WIDTH_ONE if bit == "1" else _ZERO_WIDTH_ZERO for bit in bits)
    return f"{_ZERO_WIDTH_START}{payload}{_ZERO_WIDTH_END}"


def _raw_zero_width_payload(payload: str) -> str:
    return f"{_ZERO_WIDTH_START}{payload}{_ZERO_WIDTH_END}"


def test_detector_extracts_module_created_zero_width_metadata() -> None:
    import aigc_filter

    result = aigc_filter.filter("建议派 18 辆车，瓶颈在仓库 C。")
    detected = aigc_filter.detect_watermark(result.text)

    assert detected.present is True
    assert detected.trace_id == result.trace_id
    assert detected.module_version == result.watermark.module_version
    assert detected.provider == "opticloud-aigc-filter"


def test_detector_recognizes_all_module_created_watermarks() -> None:
    import aigc_filter

    outputs = [aigc_filter.filter(f"良性优化总结 {index:03d}").text for index in range(100)]

    assert all(aigc_filter.detect_watermark(output).present for output in outputs)


def test_detector_recognizes_all_benign_dataset_outputs() -> None:
    import aigc_filter

    for prompt in BENIGN_PROMPTS:
        result = aigc_filter.filter(prompt, tier="strict")
        detected = aigc_filter.detect_watermark(result.text)

        assert detected.present is True
        assert detected.trace_id == result.watermark.trace_id
        assert detected.module_version == result.watermark.module_version
        assert detected.provider == result.watermark.provider


def test_detector_recognizes_all_red_team_blocked_outputs() -> None:
    import aigc_filter

    for prompt in RED_TEAM_PROMPTS:
        result = aigc_filter.filter(prompt, tier="strict")
        detected = aigc_filter.detect_watermark(result.text)

        assert result.blocked is True
        assert detected.present is True
        assert detected.trace_id == result.watermark.trace_id
        assert detected.module_version == result.watermark.module_version
        assert detected.provider == result.watermark.provider


@pytest.mark.parametrize(
    "text",
    [
        "中文调度摘要\n第二行包含瓶颈说明。",
        "English optimization summary with markdown-like **bold** text.",
        "混合 emoji 🚚📦 和换行\n\n- item one\n- item two",
        "长文本 " * 80,
    ],
)
def test_detector_handles_direct_watermarking_custom_trace_and_wrapping(text: str) -> None:
    import aigc_filter

    watermarked = aigc_filter.add_watermark(text, trace_id="trc_custom_trace_001")
    wrapped = f"prefix\n{watermarked}\nsuffix"
    detected = aigc_filter.detect_watermark(wrapped)
    refiltered = aigc_filter.filter(watermarked)

    assert detected.present is True
    assert detected.trace_id == "trc_custom_trace_001"
    assert detected.provider == aigc_filter.PROVIDER_MARKER
    assert refiltered.trace_id == "trc_custom_trace_001"


def test_detector_does_not_depend_on_visible_marker() -> None:
    import aigc_filter

    result = aigc_filter.filter("请总结仓库排班优化结果。")
    metadata_only = result.text.replace(aigc_filter.AIGC_VISIBLE_MARKER, "")
    detected = aigc_filter.detect_watermark(metadata_only)

    assert detected.present is True
    assert detected.trace_id == result.trace_id
    assert detected.module_version == result.watermark.module_version
    assert detected.provider == result.watermark.provider


def test_detector_scans_back_to_valid_payload_when_trailing_payload_is_corrupt() -> None:
    import aigc_filter

    result = aigc_filter.filter("请总结仓库排班优化结果。")
    with_corrupt_tail = f"{result.text}{_raw_zero_width_payload(_ZERO_WIDTH_ONE)}"
    detected = aigc_filter.detect_watermark(with_corrupt_tail)

    assert detected.present is True
    assert detected.trace_id == result.trace_id
    assert detected.module_version == result.watermark.module_version
    assert detected.provider == result.watermark.provider


def test_detector_uses_rightmost_valid_module_payload() -> None:
    import aigc_filter

    first = aigc_filter.add_watermark("first", trace_id="trc_first_payload")
    second_payload = _module_payload(
        {
            "module_version": "0.1.0",
            "provider": aigc_filter.PROVIDER_MARKER,
            "trace_id": "trc_second_payload",
        }
    )
    detected = aigc_filter.detect_watermark(f"{first} middle {second_payload}")

    assert detected.present is True
    assert detected.trace_id == "trc_second_payload"
    assert detected.module_version == "0.1.0"
    assert detected.provider == aigc_filter.PROVIDER_MARKER


def test_watermarking_is_idempotent_for_existing_module_watermark() -> None:
    import aigc_filter

    first = aigc_filter.filter("请总结这个优化结果。")
    second = aigc_filter.filter(first.text)

    assert second.text == first.text
    assert second.trace_id == first.trace_id
    assert second.watermark.trace_id == first.trace_id


def test_detector_handles_missing_or_tampered_metadata() -> None:
    import aigc_filter

    missing = aigc_filter.detect_watermark("普通文本。本回答由 AI 生成，仅供参考")
    tampered = aigc_filter.detect_watermark("\u200b\u200cnot-json\u200d")

    assert missing.present is False
    assert missing.trace_id is None
    assert tampered.present is False
    assert tampered.trace_id is None


@pytest.mark.parametrize(
    "metadata",
    [
        {"module_version": "0.1.0", "provider": "not-opticloud", "trace_id": "trc_bad"},
        {"module_version": "0.1.0", "provider": "opticloud-aigc-filter"},
        {"provider": "opticloud-aigc-filter", "trace_id": "trc_missing_version"},
        {"module_version": "0.1.0", "trace_id": "trc_missing_provider"},
        {"module_version": "0.1.0", "provider": "opticloud-aigc-filter", "trace_id": ""},
        {"module_version": "", "provider": "opticloud-aigc-filter", "trace_id": "trc_empty"},
        {"module_version": "0.1.0", "provider": "opticloud-aigc-filter", "trace_id": "not_trc"},
        {"module_version": "0.1.0", "provider": "opticloud-aigc-filter", "trace_id": 123},
        {"module_version": 1, "provider": "opticloud-aigc-filter", "trace_id": "trc_version"},
        {
            "module_version": "0.1.0",
            "provider": ["opticloud-aigc-filter"],
            "trace_id": "trc_provider",
        },
    ],
)
def test_detector_rejects_non_module_or_malformed_metadata(
    metadata: dict[str, object],
) -> None:
    import aigc_filter

    detected = aigc_filter.detect_watermark(_module_payload(metadata))

    assert detected.present is False
    assert detected.trace_id is None
    assert detected.module_version is None
    assert detected.provider is None


@pytest.mark.parametrize(
    "text",
    [
        _raw_zero_width_payload(""),
        _raw_zero_width_payload(_ZERO_WIDTH_ONE),
        _raw_zero_width_payload("not-zero-width"),
        f"{_ZERO_WIDTH_END}{_ZERO_WIDTH_ONE}{_ZERO_WIDTH_START}",
        "\u200b\u200cnot-json\u200d",
    ],
)
def test_detector_rejects_broken_payloads_without_exceptions(text: str) -> None:
    import aigc_filter

    detected = aigc_filter.detect_watermark(text)

    assert detected.present is False
    assert detected.trace_id is None
    assert detected.module_version is None
    assert detected.provider is None


def test_visible_marker_and_aria_label_are_stable() -> None:
    import aigc_filter

    result = aigc_filter.filter("输出一段 NL summary。")

    assert result.aria_label == "本回答由 AI 生成，仅供参考"
    assert result.text.count("本回答由 AI 生成，仅供参考") == 1
