"""Story 1.11 — deterministic v1 geo-anomaly helpers for API Key use.

This is intentionally small and dependency-free. v1 does not attempt real
commercial geolocation; it only recognizes known demo/test networks and treats
unknown/private/loopback IPs as non-anomalous.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from decimal import Decimal

DETECTOR_VERSION = "geo-risk-v1"
GEO_RISK_DELTA = Decimal("0.35")
MAX_RISK_SCORE = Decimal("1.00")


@dataclass(frozen=True)
class GeoBucket:
    code: str
    label_zh: str


_KNOWN_BUCKETS: tuple[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, GeoBucket], ...] = (
    (
        ipaddress.ip_network("101.6.0.0/16"),
        GeoBucket(code="CN-BJ", label_zh="中国北京"),
    ),
    (
        ipaddress.ip_network("139.59.0.0/16"),
        GeoBucket(code="SG-SG", label_zh="新加坡"),
    ),
)


def normalize_ip(ip_str: str | None) -> str | None:
    """Return normalized IP string, or None for missing/invalid inputs."""
    if not ip_str:
        return None
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return None
    return str(addr)


def bucket_for_ip(ip_str: str | None) -> GeoBucket | None:
    """Map a known public IP to a deterministic v1 bucket."""
    normalized = normalize_ip(ip_str)
    if normalized is None:
        return None
    addr = ipaddress.ip_address(normalized)
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return None
    for network, bucket in _KNOWN_BUCKETS:
        if addr in network:
            return bucket
    return None


def label_for_bucket_code(code: str | None) -> str | None:
    """Return the zh label for a known bucket code."""
    if code is None:
        return None
    for _network, bucket in _KNOWN_BUCKETS:
        if bucket.code == code:
            return bucket.label_zh
    return None


def is_geo_anomaly(previous_bucket: str | None, current_bucket: str | None) -> bool:
    """Known-to-known bucket changes are v1 anomalies."""
    return bool(previous_bucket and current_bucket and previous_bucket != current_bucket)


def next_risk_score(current_score: Decimal | float | str | None) -> Decimal:
    """Bounded additive risk score for a new geo anomaly."""
    score = Decimal("0.00") if current_score is None else Decimal(str(current_score))
    return min(MAX_RISK_SCORE, score + GEO_RISK_DELTA).quantize(Decimal("0.01"))
