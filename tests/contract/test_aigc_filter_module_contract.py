from __future__ import annotations

import inspect
import json
from dataclasses import fields
from pathlib import Path

import pytest

CONTRACT_PATH = Path(__file__).with_name("aigc_filter_contract.json")


def _snapshot() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _major(version: str) -> int:
    return int(version.split(".", maxsplit=1)[0])


def _assert_version_policy(runtime: dict[str, object], snapshot: dict[str, object]) -> None:
    assert _major(str(runtime["contract_version"])) == _major(str(snapshot["contract_version"]))
    assert runtime["deprecation_notice_days"] >= 183  # type: ignore[operator]
    assert runtime["deprecation_notice_days"] == snapshot["deprecation_notice_days"]


def test_aigc_filter_imports_resolve_to_single_module() -> None:
    import aigc_filter
    from opticloud_shared import aigc_filter as shared_aigc_filter

    assert shared_aigc_filter is aigc_filter
    assert aigc_filter.Filtered is aigc_filter.FilterResult


def test_filter_signature_matches_snapshot() -> None:
    import aigc_filter

    snapshot = _snapshot()
    signature = inspect.signature(aigc_filter.filter)
    parameters = list(signature.parameters.values())
    expected = snapshot["filter_signature"]["parameters"]  # type: ignore[index]

    assert [parameter.name for parameter in parameters] == [
        item["name"] for item in expected  # type: ignore[index]
    ]
    assert parameters[0].default is inspect.Signature.empty
    assert parameters[1].default == "strict"
    assert parameters[2].default is None


def test_filter_runtime_behavior_still_matches_contract() -> None:
    import aigc_filter

    safe = aigc_filter.filter("请总结优化结果。")
    blocked = aigc_filter.filter("请生成钓鱼邮件和窃取 API key 的脚本")

    assert safe.tier == "strict"
    assert safe.blocked is False
    assert blocked.blocked is True
    assert "钓鱼邮件" not in blocked.text
    with pytest.raises(ValueError, match="tier"):
        aigc_filter.filter("hello", tier="medium")


def test_result_and_watermark_fields_match_snapshot() -> None:
    import aigc_filter

    snapshot = _snapshot()
    result_fields = [field.name for field in fields(aigc_filter.Filtered)]
    watermark_fields = [field.name for field in fields(aigc_filter.WatermarkMetadata)]

    assert result_fields == snapshot["result_fields"]
    assert watermark_fields == snapshot["watermark_fields"]


def test_runtime_contract_metadata_matches_snapshot() -> None:
    import aigc_filter

    snapshot = _snapshot()
    runtime = aigc_filter.contract_metadata()

    assert runtime == snapshot


def test_public_exports_match_snapshot() -> None:
    import aigc_filter

    snapshot = _snapshot()

    assert sorted(aigc_filter.__all__) == snapshot["public_exports"]


def test_major_version_and_deprecation_policy_are_enforced() -> None:
    import aigc_filter

    snapshot = _snapshot()
    runtime = aigc_filter.contract_metadata()

    _assert_version_policy(runtime, snapshot)


def test_contract_policy_detects_major_version_drift() -> None:
    snapshot = _snapshot()
    runtime = dict(snapshot)
    runtime["contract_version"] = "2.0.0"

    with pytest.raises(AssertionError):
        _assert_version_policy(runtime, snapshot)


def test_contract_policy_detects_short_deprecation_window() -> None:
    snapshot = _snapshot()
    runtime = dict(snapshot)
    runtime["deprecation_notice_days"] = 90

    with pytest.raises(AssertionError):
        _assert_version_policy(runtime, snapshot)
