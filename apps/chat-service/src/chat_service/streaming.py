from __future__ import annotations

import hashlib
import json
import re
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass

import anyio
import anyio.lowlevel

from chat_service.schemas import ChatLocale, ModelPreviewStatus

MAX_CHUNK_TOKEN_UNITS = 100
COUNT_UNIT_METHOD = "content_unit_approximation"
RETRY_MILLISECONDS = 3000
FILTERED_CHUNK = "[filtered]"
_EVENT_ID_PATTERN = re.compile(r"^sse_[0-9a-f]{16}_[0-9]{6}$")
_ZERO_WIDTH_CHARS = {
    "\u200b",
    "\u200c",
    "\u200d",
    "\u2060",
}
_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]")
_NO_LEAK_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_\s-]?key|bearer\s+[A-Za-z0-9._-]+|"
    r"authorization|cookie|password|token|raw[_ -]?(?:response|request)|"
    r"provider[_ -]?(?:request|response|payload)?|prompt|traceback|"
    r"generated[_ -]?code|sandbox[_ -]?output|"
    r"charge_id|optimization_id|prediction_id|callback[_ -]?url|"
    r"[A-Za-z]:\\|/tmp/|/var/|queue[_ -]?payload)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChatStreamEvent:
    event_id: str
    event: str
    data: dict[str, object]
    retry: int = RETRY_MILLISECONDS


def build_stream_events(
    *,
    message_id: str,
    locale: ChatLocale,
    content: str,
    model_preview_id: str,
    model_preview_status: ModelPreviewStatus,
    aigc_watermark_trace_id: str,
    aigc_gate: Mapping[str, object],
) -> list[ChatStreamEvent]:
    prefix = _event_id_prefix(message_id)
    events = [
        ChatStreamEvent(
            event_id=_event_id(prefix, 0),
            event="message_start",
            data={
                "message_id": message_id,
                "mode": "internal_beta",
                "public_access": False,
                "locale": locale,
                "max_chunk_token_units": MAX_CHUNK_TOKEN_UNITS,
                "token_count_method": COUNT_UNIT_METHOD,
            },
        )
    ]

    stream_content = _safe_stream_content(strip_zero_width_metadata(content))
    chunks = split_content_chunks(stream_content, max_units=MAX_CHUNK_TOKEN_UNITS)
    for index, chunk in enumerate(chunks, start=1):
        safe_chunk = _safe_chunk(chunk)
        events.append(
            ChatStreamEvent(
                event_id=_event_id(prefix, index),
                event="content_delta",
                data={
                    "message_id": message_id,
                    "chunk_index": index - 1,
                    "chunk": safe_chunk,
                    "token_units": content_token_units(safe_chunk),
                },
            )
        )

    events.append(
        ChatStreamEvent(
            event_id=_event_id(prefix, len(events)),
            event="done",
            data={
                "message_id": message_id,
                "done": True,
                "content_event_count": len(chunks),
                "model_preview_id": model_preview_id,
                "model_preview_status": model_preview_status,
                "aigc_watermark_trace_id": aigc_watermark_trace_id,
                "aigc_gate": dict(aigc_gate),
            },
        )
    )
    return events


async def iter_sse_payload(
    events: list[ChatStreamEvent],
    *,
    last_event_id: str | None = None,
) -> AsyncIterator[str]:
    yield ":heartbeat\n\n"
    start_index = _resume_index(events, last_event_id)
    if start_index is None:
        yield format_sse_event(_invalid_cursor_event(events))
        return
    for event in events[start_index:]:
        await anyio.lowlevel.checkpoint()
        yield format_sse_event(event)


def format_sse_event(event: ChatStreamEvent) -> str:
    payload = json.dumps(
        _safe_data(event.data),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"id: {event.event_id}\nevent: {event.event}\nretry: {event.retry}\ndata: {payload}\n\n"


def split_content_chunks(text: str, *, max_units: int = MAX_CHUNK_TOKEN_UNITS) -> list[str]:
    if max_units < 1:
        raise ValueError("max_units must be positive")
    if text == FILTERED_CHUNK:
        return [FILTERED_CHUNK]
    tokens = _TOKEN_PATTERN.findall(strip_zero_width_metadata(text))
    if not tokens:
        return []
    chunks: list[str] = []
    current: list[str] = []
    for token in tokens:
        if len(current) >= max_units:
            chunks.append(_join_tokens(current))
            current = []
        current.append(token)
    if current:
        chunks.append(_join_tokens(current))
    return chunks


def content_token_units(text: str) -> int:
    return len(_TOKEN_PATTERN.findall(strip_zero_width_metadata(text)))


def strip_zero_width_metadata(text: str) -> str:
    return "".join(char for char in text if char not in _ZERO_WIDTH_CHARS).rstrip()


def _resume_index(events: list[ChatStreamEvent], last_event_id: str | None) -> int | None:
    if last_event_id is None:
        return 0
    if not _EVENT_ID_PATTERN.fullmatch(last_event_id):
        return None
    for index, event in enumerate(events):
        if event.event_id == last_event_id:
            return index + 1
    return None


def _invalid_cursor_event(events: list[ChatStreamEvent]) -> ChatStreamEvent:
    prefix = _stream_prefix_from_events(events)
    return ChatStreamEvent(
        event_id=_event_id(prefix, 999999),
        event="error",
        data={
            "error_code": "invalid_cursor",
            "message": "stream cursor is invalid for this response",
        },
    )


def _event_id_prefix(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _stream_prefix_from_events(events: list[ChatStreamEvent]) -> str:
    if events:
        parts = events[0].event_id.split("_")
        if len(parts) == 3 and parts[0] == "sse":
            return parts[1]
    return _event_id_prefix("stream")


def _event_id(prefix: str, sequence: int) -> str:
    return f"sse_{prefix}_{sequence:06d}"


def _safe_chunk(chunk: str) -> str:
    if _NO_LEAK_PATTERN.search(chunk):
        return FILTERED_CHUNK
    return chunk


def _safe_stream_content(content: str) -> str:
    if _NO_LEAK_PATTERN.search(content):
        return FILTERED_CHUNK
    return content


def _safe_data(data: dict[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, str):
            safe[key] = FILTERED_CHUNK if _NO_LEAK_PATTERN.search(value) else value
        elif isinstance(value, dict):
            safe[key] = _safe_data(
                {str(child_key): child_value for child_key, child_value in value.items()}
            )
        else:
            safe[key] = value
    return safe


def _join_tokens(tokens: list[str]) -> str:
    output = ""
    for token in tokens:
        if not output:
            output = token
        elif _is_cjk(token) or _ends_with_cjk(output) or _is_punctuation(token):
            output += token
        else:
            output += f" {token}"
    return output


def _is_cjk(token: str) -> bool:
    return len(token) == 1 and "\u4e00" <= token <= "\u9fff"


def _ends_with_cjk(text: str) -> bool:
    return bool(text and "\u4e00" <= text[-1] <= "\u9fff")


def _is_punctuation(token: str) -> bool:
    return len(token) == 1 and not token.isalnum() and not _is_cjk(token)
