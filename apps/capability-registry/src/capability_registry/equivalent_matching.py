"""Pure equivalent capability matching and ranking helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

RANKING_VERSION = "capability-equivalent-matching-v1"
ELIGIBLE_CAPABILITY_STATUSES = frozenset({"v1", "v1_late", "v2", "audited"})
ACTIVE_PROVIDER_STATUS = "active"
REJECTION_KEYS: tuple[str, ...] = (
    "source_excluded",
    "task_type_mismatch",
    "tag_mismatch",
    "solver_mismatch",
    "provider_missing",
    "provider_not_active",
    "capability_not_eligible",
    "invalid_precision",
)
_PRECISION_QUANT = Decimal("0.000001")


@dataclass(frozen=True)
class EquivalentCapabilitySnapshot:
    """Safe capability/provider fields required for equivalent matching."""

    k_algo: str
    task_type: str
    provider_id: str
    provider_kind: str
    provider_url: str
    provider_status: str | None
    model_version: str
    capability_status: str
    supported_solvers: tuple[str, ...]
    tags: tuple[str, ...]
    metadata: dict[str, Any]
    scope_source: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_solvers", tuple(sorted(set(self.supported_solvers))))
        object.__setattr__(self, "tags", tuple(sorted(set(self.tags))))


@dataclass(frozen=True)
class VersionDistance:
    parseable: bool
    distance: int | None

    @property
    def sort_key(self) -> tuple[int, int]:
        if not self.parseable or self.distance is None:
            return (1, 0)
        return (0, self.distance)

    def to_response(self) -> dict[str, Any]:
        return {"parseable": self.parseable, "distance": self.distance}


@dataclass(frozen=True)
class RankedEquivalentCandidate:
    rank: int
    snapshot: EquivalentCapabilitySnapshot
    precision: Decimal
    version_distance: VersionDistance
    score: Decimal

    def to_response(self) -> dict[str, Any]:
        score = _decimal_response(self.score)
        precision = _decimal_response(self.precision)
        return {
            "rank": self.rank,
            "k_algo": self.snapshot.k_algo,
            "provider_id": self.snapshot.provider_id,
            "model_version": self.snapshot.model_version,
            "provider_kind": self.snapshot.provider_kind,
            "provider_url": self.snapshot.provider_url,
            "task_type": self.snapshot.task_type,
            "supported_solvers": list(self.snapshot.supported_solvers),
            "tags": list(self.snapshot.tags),
            "precision": precision,
            "version_distance": self.version_distance.to_response(),
            "score": score,
            "score_breakdown": {
                "precision": precision,
                "version_distance": self.version_distance.to_response(),
                "provider_kind": self.snapshot.provider_kind,
            },
            "scope_source": self.snapshot.scope_source,
        }


@dataclass(frozen=True)
class EquivalentMatchingResult:
    ranking_version: str
    source: EquivalentCapabilitySnapshot
    solver: str
    required_tags: tuple[str, ...]
    total_candidates_considered: int
    rejection_counts: dict[str, int]
    candidates: tuple[RankedEquivalentCandidate, ...]

    def to_response(self) -> dict[str, Any]:
        return {
            "ranking_version": self.ranking_version,
            "source": _source_response(self.source),
            "solver": self.solver,
            "required_tags": list(self.required_tags),
            "total_candidates_considered": self.total_candidates_considered,
            "rejection_counts": dict(self.rejection_counts),
            "candidates": [candidate.to_response() for candidate in self.candidates],
        }


def match_equivalent_capabilities(
    *,
    source: EquivalentCapabilitySnapshot,
    candidates: tuple[EquivalentCapabilitySnapshot, ...],
    solver: str,
    max_results: int,
    include_source: bool = False,
) -> EquivalentMatchingResult:
    """Rank equivalent capability candidates using deterministic, auditable rules."""
    rejection_counts = dict.fromkeys(REJECTION_KEYS, 0)
    source_tags = tuple(sorted(source.tags))
    total_candidates_considered = len(candidates)
    ranked: list[
        tuple[tuple[Any, ...], EquivalentCapabilitySnapshot, Decimal, VersionDistance]
    ] = []
    for candidate in candidates:
        precision = _precision(candidate.metadata)
        if not include_source and candidate.k_algo == source.k_algo:
            rejection_counts["source_excluded"] += 1
            continue
        if candidate.task_type != source.task_type:
            rejection_counts["task_type_mismatch"] += 1
            continue
        if tuple(sorted(candidate.tags)) != source_tags:
            rejection_counts["tag_mismatch"] += 1
            continue
        if solver not in candidate.supported_solvers:
            rejection_counts["solver_mismatch"] += 1
            continue
        if candidate.provider_status is None:
            rejection_counts["provider_missing"] += 1
            continue
        if candidate.provider_status != ACTIVE_PROVIDER_STATUS:
            rejection_counts["provider_not_active"] += 1
            continue
        if candidate.capability_status not in ELIGIBLE_CAPABILITY_STATUSES:
            rejection_counts["capability_not_eligible"] += 1
            continue
        if precision is None:
            rejection_counts["invalid_precision"] += 1
            continue
        version_distance = semantic_version_distance(source.model_version, candidate.model_version)
        same_kind_rank = 0 if candidate.provider_kind == source.provider_kind else 1
        sort_key = (
            -precision,
            version_distance.sort_key,
            same_kind_rank,
            candidate.provider_id,
            candidate.model_version,
            candidate.k_algo,
        )
        ranked.append((sort_key, candidate, precision, version_distance))
    ranked.sort(key=lambda item: item[0])
    limited = ranked[:max_results]
    candidates_response = tuple(
        RankedEquivalentCandidate(
            rank=index,
            snapshot=candidate,
            precision=precision,
            version_distance=version_distance,
            score=_score(precision, version_distance),
        )
        for index, (_, candidate, precision, version_distance) in enumerate(limited, start=1)
    )
    return EquivalentMatchingResult(
        ranking_version=RANKING_VERSION,
        source=source,
        solver=solver,
        required_tags=source_tags,
        total_candidates_considered=total_candidates_considered,
        rejection_counts=rejection_counts,
        candidates=candidates_response,
    )


def semantic_version_distance(source: str, candidate: str) -> VersionDistance:
    source_version = _parse_semver(source)
    candidate_version = _parse_semver(candidate)
    if source_version is None or candidate_version is None:
        return VersionDistance(parseable=False, distance=None)
    distance = (
        abs(source_version[0] - candidate_version[0]) * 1_000_000
        + abs(source_version[1] - candidate_version[1]) * 1_000
        + abs(source_version[2] - candidate_version[2])
    )
    return VersionDistance(parseable=True, distance=distance)


def _parse_semver(value: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$", value)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _precision(metadata: dict[str, Any]) -> Decimal | None:
    value: Any = None
    matching = metadata.get("matching")
    if isinstance(matching, dict) and "precision" in matching:
        value = matching["precision"]
    elif "precision" in metadata:
        value = metadata["precision"]
    else:
        return Decimal("0").quantize(_PRECISION_QUANT)
    if isinstance(value, bool) or isinstance(value, str):
        return None
    try:
        precision = Decimal(str(value)).quantize(_PRECISION_QUANT)
    except (InvalidOperation, ValueError):
        return None
    if precision < 0 or precision > 1:
        return None
    return precision


def _score(precision: Decimal, version_distance: VersionDistance) -> Decimal:
    if not version_distance.parseable or version_distance.distance is None:
        version_component = Decimal("0")
    else:
        version_component = Decimal("1") / (Decimal("1") + Decimal(version_distance.distance))
    return (precision * Decimal("0.990000") + version_component * Decimal("0.010000")).quantize(
        _PRECISION_QUANT
    )


def _decimal_response(value: Decimal) -> str:
    return f"{value.quantize(_PRECISION_QUANT):.6f}"


def _source_response(source: EquivalentCapabilitySnapshot) -> dict[str, Any]:
    return {
        "k_algo": source.k_algo,
        "provider_id": source.provider_id,
        "model_version": source.model_version,
        "provider_kind": source.provider_kind,
        "provider_url": source.provider_url,
        "task_type": source.task_type,
        "supported_solvers": list(source.supported_solvers),
        "tags": list(source.tags),
        "scope_source": source.scope_source,
    }
