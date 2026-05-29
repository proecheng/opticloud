from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence

from chat_service.schemas import (
    ChatFileContext,
    ChatFileContextPreview,
    ChatFileSheetContext,
)

PROMPT_SUMMARY_MAX_CHARS = 700
FILTERED_VALUE = "[filtered]"
_NO_LEAK_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_\s-]?key|bearer\s+[A-Za-z0-9._-]+|"
    r"authorization|cookie|password|token|raw[_ -]?(?:response|request|row|value)|"
    r"provider[_ -]?(?:request|response|payload)?|prompt|traceback|"
    r"generated[_ -]?code|sandbox[_ -]?output|"
    r"charge_id|optimization_id|prediction_id|callback[_ -]?url|"
    r"[A-Za-z]:\\|/tmp/|/var/|queue[_ -]?payload)",
    re.IGNORECASE,
)


def sanitize_file_contexts(contexts: Sequence[ChatFileContext]) -> list[ChatFileContext]:
    sanitized: list[ChatFileContext] = []
    for context in contexts[:3]:
        sheets = [
            ChatFileSheetContext(
                name=_safe_term(sheet.name),
                headers=_safe_terms(sheet.headers, max_items=20),
                row_count=sheet.row_count,
            )
            for sheet in context.sheets[:12]
            if _safe_term(sheet.name) != FILTERED_VALUE
        ]
        detected_fields = _safe_terms(
            [
                *context.detected_fields,
                *context.top_level_keys,
                *(header for sheet in sheets for header in sheet.headers),
            ],
            max_items=30,
        )
        top_level_keys = _safe_terms(context.top_level_keys, max_items=30)
        sanitized.append(
            ChatFileContext(
                source=context.source,
                kind=context.kind,
                filename=_safe_filename(context.filename),
                size_bytes=context.size_bytes,
                mime_type=_safe_mime_type(context.mime_type),
                row_count=context.row_count,
                sheet_count=len(sheets) if context.kind == "excel" else 0,
                sheets=sheets if context.kind == "excel" else [],
                top_level_keys=top_level_keys if context.kind == "json" else [],
                detected_fields=detected_fields,
                summary=_safe_summary(context.summary),
            )
        )
    return sanitized


def canonical_file_context_digest(contexts: Sequence[ChatFileContext]) -> str:
    sanitized = sanitize_file_contexts(contexts)
    if not sanitized:
        return ""
    entries = [
        (
            context.kind,
            context.filename,
            context.size_bytes,
            context.summary,
            json.dumps(
                context.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
        for context in sanitized
    ]
    payload = [entry[-1] for entry in sorted(entries)]
    canonical = f"[{','.join(payload)}]"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_file_context_preview(
    contexts: Sequence[ChatFileContext],
) -> ChatFileContextPreview | None:
    sanitized = sanitize_file_contexts(contexts)
    if not sanitized:
        return None
    detected_fields = sorted(
        {
            field
            for context in sanitized
            for field in [*context.detected_fields, *context.top_level_keys]
            if field != FILTERED_VALUE
        }
    )[:30]
    return ChatFileContextPreview(
        file_count=len(sanitized),
        kinds=sorted({context.kind for context in sanitized}),
        total_rows=sum(context.row_count for context in sanitized),
        filenames=[context.filename for context in sanitized],
        detected_fields=detected_fields,
    )


def build_file_context_prompt_summary(contexts: Sequence[ChatFileContext]) -> str:
    sanitized = sanitize_file_contexts(contexts)
    if not sanitized:
        return ""
    parts: list[str] = []
    for context in sanitized:
        fields = ", ".join(context.detected_fields[:8])
        if context.kind == "excel":
            sheet_labels = ", ".join(
                f"{sheet.name}({', '.join(sheet.headers[:6])})" for sheet in context.sheets[:4]
            )
            parts.append(
                f"{context.kind} file {context.filename}: rows={context.row_count}, "
                f"sheets={context.sheet_count}, sheet_headers=[{sheet_labels}]"
            )
        elif context.kind == "json":
            keys = ", ".join(context.top_level_keys[:10])
            parts.append(
                f"{context.kind} file {context.filename}: rows={context.row_count}, "
                f"top_level_keys=[{keys}], detected_fields=[{fields}]"
            )
        else:
            parts.append(
                f"{context.kind} file {context.filename}: rows={context.row_count}, "
                f"detected_fields=[{fields}]"
            )
    return " | ".join(parts)[:PROMPT_SUMMARY_MAX_CHARS]


def build_message_with_file_context(
    message: str,
    contexts: Sequence[ChatFileContext],
) -> str:
    summary = build_file_context_prompt_summary(contexts)
    if not summary:
        return message
    return f"{message}\n\n[uploaded_file_context]\n{summary}"


def _safe_filename(value: str) -> str:
    clean = _safe_term(value, max_chars=120)
    return "file" if clean == FILTERED_VALUE else clean


def _safe_mime_type(value: str) -> str:
    clean = _safe_term(value.lower(), max_chars=100)
    return "application/octet-stream" if clean == FILTERED_VALUE else clean


def _safe_summary(value: str) -> str:
    clean = value.strip()[:240]
    return FILTERED_VALUE if _NO_LEAK_PATTERN.search(clean) else clean


def _safe_terms(values: Sequence[str], *, max_items: int) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = _safe_term(value)
        if clean == FILTERED_VALUE or clean in seen:
            continue
        output.append(clean)
        seen.add(clean)
        if len(output) >= max_items:
            break
    return output


def _safe_term(value: str, *, max_chars: int = 64) -> str:
    clean = value.strip()[:max_chars]
    if (
        not clean
        or _NO_LEAK_PATTERN.search(clean)
        or any(char in clean for char in "\r\n\t")
        or "/" in clean
        or "\\" in clean
        or ":" in clean
        or ".." in clean
    ):
        return FILTERED_VALUE
    return clean
