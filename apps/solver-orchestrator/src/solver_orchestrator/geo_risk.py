"""Story 1.11 — deterministic coarse geo anomaly detection for API Key use."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

GEO_ANOMALY_RULE_CODE = "geo_anomaly"
GEO_ANOMALY_SCORE = 0.70


@dataclass(frozen=True)
class GeoRegion:
    code: str
    label_zh: str


@dataclass(frozen=True)
class GeoAnomaly:
    previous_ip: str
    current_ip: str
    previous_geo: GeoRegion
    current_geo: GeoRegion
    reason: str
    score: float = GEO_ANOMALY_SCORE


_NETWORKS: tuple[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, GeoRegion], ...] = (
    (ipaddress.ip_network("101.6.0.0/16"), GeoRegion("CN-BJ", "中国北京")),
    (ipaddress.ip_network("13.250.0.0/15"), GeoRegion("SG", "新加坡")),
    (ipaddress.ip_network("8.8.8.0/24"), GeoRegion("US", "美国")),
)


def resolve_coarse_geo(ip_value: str | None) -> GeoRegion | None:
    """Resolve known public IPv4 test ranges to coarse regions.

    Unknown, private, loopback, reserved, malformed, and IPv6 values return None.
    """
    if not ip_value:
        return None
    try:
        address = ipaddress.ip_address(ip_value)
    except ValueError:
        return None
    if not isinstance(address, ipaddress.IPv4Address):
        return None
    if (
        address.is_private
        or address.is_loopback
        or address.is_reserved
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
    ):
        return None

    for network, region in _NETWORKS:
        if address in network:
            return region
    return None


def assess_geo_anomaly(previous_ip: str | None, current_ip: str | None) -> GeoAnomaly | None:
    """Return a geo anomaly only when both IPs map to known different regions."""
    if not previous_ip or not current_ip:
        return None
    previous_geo = resolve_coarse_geo(previous_ip)
    current_geo = resolve_coarse_geo(current_ip)
    if previous_geo is None or current_geo is None:
        return None
    if previous_geo.code == current_geo.code:
        return None
    return GeoAnomaly(
        previous_ip=previous_ip,
        current_ip=current_ip,
        previous_geo=previous_geo,
        current_geo=current_geo,
        reason=f"api_key_geo_changed:{previous_geo.code}->{current_geo.code}",
    )
