from __future__ import annotations


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


def test_visible_marker_and_aria_label_are_stable() -> None:
    import aigc_filter

    result = aigc_filter.filter("输出一段 NL summary。")

    assert result.aria_label == "本回答由 AI 生成，仅供参考"
    assert result.text.count("本回答由 AI 生成，仅供参考") == 1
