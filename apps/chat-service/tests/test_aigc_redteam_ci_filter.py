from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CI_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_chat_service_ci_runs_on_aigc_filter_and_dataset_changes() -> None:
    ci = CI_PATH.read_text(encoding="utf-8")
    chat_service_filter = _extract_filter_block(ci, "chat_service")

    assert "packages/shared-py/aigc_filter/**" in chat_service_filter
    assert "tests/aigc/**" in chat_service_filter
    assert "apps/chat-service/**" in chat_service_filter


def test_aigc_module_gate_remains_separate_from_chat_integration_gate() -> None:
    ci = CI_PATH.read_text(encoding="utf-8")
    aigc_filter_block = _extract_filter_block(ci, "aigc_filter")

    assert "packages/shared-py/aigc_filter/**" in aigc_filter_block
    assert "tests/aigc/**" in aigc_filter_block
    assert "scripts/report_aigc_filter_metrics.py" in aigc_filter_block


def _extract_filter_block(ci: str, name: str) -> str:
    pattern = re.compile(
        rf"^            {re.escape(name)}:\n(?P<body>(?:              - .+\n)+)",
        re.MULTILINE,
    )
    match = pattern.search(ci)
    assert match is not None
    return match.group("body")
