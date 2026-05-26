"""Deterministic AIGC output filter and watermark utilities.

Story M3.4 intentionally keeps this module offline and dependency-light. Later
service stories can add LLM-backed review behind this public contract.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

__version__ = "0.1.0"

Tier = Literal["strict", "loose"]

AIGC_CONTRACT_NAME = "aigc_filter_module"
AIGC_CONTRACT_VERSION = "1.0.0"
AIGC_DEPRECATION_NOTICE_DAYS = 183
AIGC_ARIA_LABEL = "本回答由 AI 生成，仅供参考"
AIGC_VISIBLE_MARKER = "本回答由 AI 生成，仅供参考"
INTERNAL_SCOPE_HEADER = "X-OptiCloud-Internal-Scope"
INTERNAL_SCOPE_VALUE = "aigc-filter-self-loop"
PROVIDER_MARKER = "opticloud-aigc-filter"

_ZERO_WIDTH_START = "\u200b"
_ZERO_WIDTH_ZERO = "\u200c"
_ZERO_WIDTH_ONE = "\u200d"
_ZERO_WIDTH_END = "\u2060"
_BLOCKED_TEXT = "内容因安全与合规策略已被拦截。"

_BASE_BLOCK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"违法|逃避追踪|爆炸物|制作爆炸|武器|攻击步骤", "illegal_harmful_instruction"),
    (r"仇恨|歧视|攻击话术|目标群体", "hate_or_harassment"),
    (r"钓鱼|窃取|盗取|api\s*key|密码|凭证|木马|恶意脚本", "credential_or_cyber_abuse"),
    (r"绕过平台审查|绕过审查|规避审查", "policy_evasion"),
)
_STRICT_ONLY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"灰产|绕过风控|黑产|薅羊毛脚本", "strict_policy"),
)


@dataclass(frozen=True)
class WatermarkMetadata:
    """Metadata encoded in zero-width watermark payloads."""

    trace_id: str
    module_version: str
    provider: str


@dataclass(frozen=True)
class FilterResult:
    """AIGC filter result returned to future Chat/Critic callers."""

    text: str
    blocked: bool
    reason_codes: tuple[str, ...]
    tier: Tier
    trace_id: str
    aria_label: str
    watermark: WatermarkMetadata
    metadata: dict[str, object]


Filtered = FilterResult


@dataclass(frozen=True)
class WatermarkDetection:
    """Detector result for module-created zero-width watermarks."""

    present: bool
    trace_id: str | None = None
    module_version: str | None = None
    provider: str | None = None


def filter(  # noqa: A001 - public API intentionally matches epics.md
    text: str,
    tier: Tier = "strict",
    context: Mapping[str, str] | None = None,
) -> FilterResult:
    """Filter user-visible NL output and append compliance watermark metadata."""

    normalized_tier = _validate_tier(tier)
    existing = detect_watermark(text)
    reasons = _reason_codes(text, normalized_tier)
    blocked = bool(reasons)
    if existing.present and existing.trace_id is not None:
        trace_id = existing.trace_id
        clean_text = add_watermark(_BLOCKED_TEXT, trace_id=trace_id) if blocked else text
    else:
        trace_id = _trace_id_for(text)
        clean_text = _BLOCKED_TEXT if reasons else text
        clean_text = add_watermark(clean_text, trace_id=trace_id)

    watermark = WatermarkMetadata(
        trace_id=trace_id,
        module_version=existing.module_version or __version__,
        provider=existing.provider or PROVIDER_MARKER,
    )
    return FilterResult(
        text=clean_text,
        blocked=blocked,
        reason_codes=reasons,
        tier=normalized_tier,
        trace_id=trace_id,
        aria_label=AIGC_ARIA_LABEL,
        watermark=watermark,
        metadata={"self_loop_bypass": is_internal_self_loop(context or {})},
    )


def add_watermark(text: str, *, trace_id: str | None = None) -> str:
    """Append visible marker and zero-width metadata once."""

    detected = detect_watermark(text)
    if detected.present:
        return text

    effective_trace_id = trace_id or _trace_id_for(text)
    visible = text
    if AIGC_VISIBLE_MARKER not in visible:
        visible = f"{visible}\n\n{AIGC_VISIBLE_MARKER}"
    metadata = {
        "trace_id": effective_trace_id,
        "module_version": __version__,
        "provider": PROVIDER_MARKER,
    }
    return f"{visible}{_encode_zero_width(metadata)}"


def detect_watermark(text: str) -> WatermarkDetection:
    """Detect and decode module-created zero-width watermark metadata."""

    payload = _extract_zero_width_payload(text)
    if payload is None:
        return WatermarkDetection(present=False)
    try:
        decoded = _decode_zero_width(payload)
        raw = json.loads(decoded)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return WatermarkDetection(present=False)
    if raw.get("provider") != PROVIDER_MARKER or not isinstance(raw.get("trace_id"), str):
        return WatermarkDetection(present=False)
    return WatermarkDetection(
        present=True,
        trace_id=raw["trace_id"],
        module_version=str(raw.get("module_version", "")),
        provider=raw["provider"],
    )


def is_internal_self_loop(context: Mapping[str, str]) -> bool:
    """Return whether context marks an internal AIGC-filter self-loop call."""

    return context.get(INTERNAL_SCOPE_HEADER) == INTERNAL_SCOPE_VALUE


def contract_metadata() -> dict[str, object]:
    """Return the stable module contract used by PR contract tests."""

    return {
        "contract_name": AIGC_CONTRACT_NAME,
        "contract_version": AIGC_CONTRACT_VERSION,
        "deprecation_notice_days": AIGC_DEPRECATION_NOTICE_DAYS,
        "filter_signature": {
            "parameters": [
                {"name": "text", "required": True},
                {"default": "strict", "name": "tier", "required": False},
                {"default": None, "name": "context", "required": False},
            ]
        },
        "public_exports": sorted(__all__),
        "result_fields": [
            "text",
            "blocked",
            "reason_codes",
            "tier",
            "trace_id",
            "aria_label",
            "watermark",
            "metadata",
        ],
        "watermark_fields": ["trace_id", "module_version", "provider"],
    }


def _validate_tier(tier: str) -> Tier:
    if tier not in ("strict", "loose"):
        raise ValueError("tier must be 'strict' or 'loose'")
    return tier  # type: ignore[return-value]


def _reason_codes(text: str, tier: Tier) -> tuple[str, ...]:
    normalized = text.lower()
    patterns = list(_BASE_BLOCK_PATTERNS)
    if tier == "strict":
        patterns.extend(_STRICT_ONLY_PATTERNS)
    reasons: list[str] = []
    for pattern, code in patterns:
        if re.search(pattern, normalized, flags=re.IGNORECASE) and code not in reasons:
            reasons.append(code)
    if reasons:
        reasons.append("blocked_content")
    return tuple(reasons)


def _trace_id_for(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"trc_{digest}"


def _encode_zero_width(metadata: Mapping[str, str]) -> str:
    raw = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    bits = "".join(f"{ord(char):08b}" for char in encoded)
    zw_payload = "".join(_ZERO_WIDTH_ONE if bit == "1" else _ZERO_WIDTH_ZERO for bit in bits)
    return f"{_ZERO_WIDTH_START}{zw_payload}{_ZERO_WIDTH_END}"


def _extract_zero_width_payload(text: str) -> str | None:
    start = text.rfind(_ZERO_WIDTH_START)
    end = text.rfind(_ZERO_WIDTH_END)
    if start == -1 or end == -1 or end <= start:
        return None
    payload = text[start + 1 : end]
    if not payload or any(char not in {_ZERO_WIDTH_ZERO, _ZERO_WIDTH_ONE} for char in payload):
        return None
    return payload


def _decode_zero_width(payload: str) -> str:
    bits = "".join("1" if char == _ZERO_WIDTH_ONE else "0" for char in payload)
    if len(bits) % 8 != 0:
        raise ValueError("invalid zero-width payload bit length")
    encoded = "".join(chr(int(bits[index : index + 8], 2)) for index in range(0, len(bits), 8))
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(f"{encoded}{padding}").decode("utf-8")


__all__ = [
    "AIGC_ARIA_LABEL",
    "AIGC_CONTRACT_NAME",
    "AIGC_CONTRACT_VERSION",
    "AIGC_DEPRECATION_NOTICE_DAYS",
    "AIGC_VISIBLE_MARKER",
    "FilterResult",
    "Filtered",
    "INTERNAL_SCOPE_HEADER",
    "INTERNAL_SCOPE_VALUE",
    "PROVIDER_MARKER",
    "WatermarkDetection",
    "WatermarkMetadata",
    "add_watermark",
    "contract_metadata",
    "detect_watermark",
    "filter",
    "is_internal_self_loop",
]
