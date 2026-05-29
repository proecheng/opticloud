from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = REPO_ROOT / "docs" / "runbooks" / "sandbox-logs-stream-v1-5-handoff.md"


def test_sandbox_logs_stream_handoff_is_linear_ready_and_deferred() -> None:
    text = HANDOFF_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    for required in [
        "Title: Implement sandbox stdout/stderr SSE logs streaming for v1.5+",
        "Stage: M7-M8 / v1.5+",
        "Owner: Chat Platform / Sandbox Runner / SDK Integration",
        "logs_stream_deferred",
        "Architecture P28",
        "Architecture P58",
        "Architecture P60",
        "api-gateway streaming proxy",
        "heartbeat",
        "reconnect cursor",
        "AIGC/filter chunk-boundary",
        "stdout/stderr redaction",
        "operator evidence",
    ]:
        assert required in text

    assert "current contract" in lower_text
    assert "deferred" in lower_text
    assert "does not implement sse" in lower_text
    assert "no current sdk streaming method" in lower_text


def test_sandbox_logs_stream_handoff_does_not_claim_current_streaming_or_real_ticket() -> None:
    text = HANDOFF_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    forbidden_claims = [
        "sse is implemented",
        "sse has been implemented",
        "sdk streaming is implemented",
        "streaming route is live",
        "production evidence",
        "linear api token",
        "lin-",
    ]

    for forbidden in forbidden_claims:
        assert forbidden not in lower_text
