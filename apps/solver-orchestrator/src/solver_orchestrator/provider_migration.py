"""Provider auto-migration resolver for reproduction reruns (Story 6.C.1)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from solver_orchestrator.catalog import CATALOG, Algorithm, ModelVersion, self_audit_passed

ProviderKind = Literal["self", "open_source", "external", "commercial"]
ProviderLifecycleStatus = Literal[
    "active", "inactive", "deprecated", "exiting", "retired", "unavailable"
]

ACTIVE_PROVIDER_STATUSES: frozenset[ProviderLifecycleStatus] = frozenset({"active"})
MIGRATION_REQUIRED_STATUSES: frozenset[ProviderLifecycleStatus] = frozenset(
    {"inactive", "deprecated", "exiting", "retired", "unavailable"}
)
PROVIDER_MIGRATION_RANKING_VERSION = "provider-migration-v1"


class ProviderMigrationStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    MIGRATED = "migrated"
    NO_EQUIVALENT = "no_equivalent"


@dataclass(frozen=True)
class ProviderCapabilitySnapshot:
    k_algo: str
    task_type: str
    provider_id: str
    provider_kind: str
    provider_url: str
    version: str
    lifecycle_status: ProviderLifecycleStatus
    supported_solvers: tuple[str, ...]
    capability_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "capability_tags",
            tuple(sorted({normalize_capability_tag(tag) for tag in self.capability_tags})),
        )
        object.__setattr__(
            self,
            "supported_solvers",
            tuple(str(solver) for solver in self.supported_solvers),
        )

    @property
    def model_version(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "kind": self.provider_kind,
            "version": self.version,
            "provider_url": self.provider_url,
        }


@dataclass(frozen=True)
class ProviderMigrationResult:
    status: ProviderMigrationStatus
    selected_model_version: dict[str, Any] | None
    response_metadata: dict[str, Any] | None


def normalize_capability_tag(value: str) -> str:
    """Normalize a capability vocabulary tag without importing capability-registry."""
    normalized = value.strip().lower().replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_-]+", "_", normalized)
    normalized = re.sub(r"[_-]{2,}", "_", normalized).strip("_-")
    if not normalized:
        raise ValueError("capability tag must not normalize to empty")
    return normalized


def default_capability_tags(task_type: str) -> tuple[str, ...]:
    raw_tags = [task_type]
    if task_type == "lp":
        raw_tags.append("linear_programming")
    if task_type == "milp":
        raw_tags.append("mixed_integer_linear_programming")
    if task_type == "vrptw":
        raw_tags.append("vrptw_with_time_windows")
    if task_type == "forecast":
        raw_tags.append("time_series_forecast")
    return tuple(sorted({normalize_capability_tag(tag) for tag in raw_tags}))


def _coerce_lifecycle_status(value: object) -> ProviderLifecycleStatus:
    if value in (
        "active",
        "inactive",
        "deprecated",
        "exiting",
        "retired",
        "unavailable",
    ):
        return value
    return "active"


def _algorithm_lifecycle_status(algo: Algorithm) -> ProviderLifecycleStatus:
    algo_payload: dict[str, Any] = dict(algo)
    raw_status = algo_payload.get("provider_lifecycle_status")
    return _coerce_lifecycle_status(raw_status)


def _algorithm_capability_tags(algo: Algorithm) -> tuple[str, ...]:
    algo_payload: dict[str, Any] = dict(algo)
    raw_tags = algo_payload.get("capability_tags")
    if isinstance(raw_tags, list | tuple):
        normalized: set[str] = set()
        for tag in raw_tags:
            if isinstance(tag, str):
                normalized.add(normalize_capability_tag(tag))
        if normalized:
            return tuple(sorted(normalized))
    return default_capability_tags(str(algo["task_type"]))


def build_catalog_provider_snapshot(items: list[Algorithm] | None = None) -> tuple[
    ProviderCapabilitySnapshot, ...
]:
    """Build the local provider/capability snapshot from solver-orchestrator catalog."""
    source = CATALOG if items is None else items
    rows: list[ProviderCapabilitySnapshot] = []
    for algo in source:
        if not self_audit_passed(algo):
            continue
        model_version: ModelVersion = algo["model_version"]
        rows.append(
            ProviderCapabilitySnapshot(
                k_algo=str(algo["k_algo"]),
                task_type=str(algo["task_type"]),
                provider_id=str(model_version["provider_id"]),
                provider_kind=str(model_version["kind"]),
                provider_url=str(model_version["provider_url"]),
                version=str(model_version["version"]),
                lifecycle_status=_algorithm_lifecycle_status(algo),
                supported_solvers=tuple(str(solver) for solver in algo["supported_solvers"]),
                capability_tags=_algorithm_capability_tags(algo),
            )
        )
    return tuple(rows)


def _find_source_row(
    *,
    locked_provider_id: str,
    task_type: str,
    snapshot: tuple[ProviderCapabilitySnapshot, ...],
) -> ProviderCapabilitySnapshot | None:
    matches = [
        row
        for row in snapshot
        if row.provider_id == locked_provider_id and row.task_type == task_type
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda row: (row.k_algo, row.version))[0]


def _semantic_version(value: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$", value)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _version_distance(source: str, candidate: str) -> tuple[int, int]:
    source_semver = _semantic_version(source)
    candidate_semver = _semantic_version(candidate)
    if source_semver is None or candidate_semver is None:
        return (1, 0)
    return (
        0,
        abs(source_semver[0] - candidate_semver[0]) * 1_000_000
        + abs(source_semver[1] - candidate_semver[1]) * 1_000
        + abs(source_semver[2] - candidate_semver[2]),
    )


def _candidate_sort_key(
    row: ProviderCapabilitySnapshot,
    *,
    locked_kind: str,
    locked_version: str,
) -> tuple[int, tuple[int, int], str, str, str]:
    return (
        0 if row.provider_kind == locked_kind else 1,
        _version_distance(locked_version, row.version),
        row.provider_id,
        row.version,
        row.k_algo,
    )


def _safe_provider_metadata(
    *,
    model_version: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    return {
        "provider_id": str(model_version.get("provider_id", "")),
        "kind": str(model_version.get("kind", "")),
        "version": str(model_version.get("version", "")),
        "provider_url": str(model_version.get("provider_url", "")),
        "status": status,
    }


def _migration_metadata(
    *,
    status: ProviderMigrationStatus,
    reason: str,
    task_type: str,
    locked_solver: str,
    capability_tags: tuple[str, ...],
    source_provider: dict[str, Any],
    selected_provider: dict[str, Any] | None,
    candidates_considered: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status.value,
        "reason": reason,
        "ranking_version": PROVIDER_MIGRATION_RANKING_VERSION,
        "task_type": task_type,
        "locked_solver": locked_solver,
        "capability_tags": list(capability_tags),
        "source_provider": source_provider,
        "candidates_considered": candidates_considered,
    }
    if selected_provider is not None:
        payload["selected_provider"] = selected_provider
    return payload


def _source_status(source_row: ProviderCapabilitySnapshot | None) -> ProviderLifecycleStatus:
    return "unavailable" if source_row is None else source_row.lifecycle_status


def _source_tags(source_row: ProviderCapabilitySnapshot | None, *, task_type: str) -> tuple[str, ...]:
    if source_row is not None:
        return source_row.capability_tags
    return default_capability_tags(task_type)


def resolve_provider_migration(
    *,
    locked_model_version: dict[str, Any],
    task_type: str,
    locked_solver: str,
    snapshot: list[ProviderCapabilitySnapshot] | tuple[ProviderCapabilitySnapshot, ...] | None = None,
) -> ProviderMigrationResult:
    """Resolve whether rerun should keep or migrate the locked Provider."""
    rows = build_catalog_provider_snapshot() if snapshot is None else tuple(snapshot)
    locked_provider_id = str(locked_model_version.get("provider_id", ""))
    locked_kind = str(locked_model_version.get("kind", ""))
    locked_version = str(locked_model_version.get("version", ""))
    source_row = _find_source_row(
        locked_provider_id=locked_provider_id,
        task_type=task_type,
        snapshot=rows,
    )
    source_status = _source_status(source_row)
    source_tags = _source_tags(source_row, task_type=task_type)
    source_provider = _safe_provider_metadata(
        model_version=locked_model_version,
        status=source_status,
    )

    if source_row is not None and source_status in ACTIVE_PROVIDER_STATUSES:
        return ProviderMigrationResult(
            status=ProviderMigrationStatus.NOT_REQUIRED,
            selected_model_version=dict(locked_model_version),
            response_metadata=None,
        )

    candidates = [
        row
        for row in rows
        if row.task_type == task_type
        and row.provider_id != locked_provider_id
        and row.lifecycle_status in ACTIVE_PROVIDER_STATUSES
        and locked_solver in row.supported_solvers
        and row.capability_tags == source_tags
    ]
    if not candidates:
        return ProviderMigrationResult(
            status=ProviderMigrationStatus.NO_EQUIVALENT,
            selected_model_version=None,
            response_metadata=_migration_metadata(
                status=ProviderMigrationStatus.NO_EQUIVALENT,
                reason="no active equivalent provider matched task_type, locked_solver, and capability_tags",
                task_type=task_type,
                locked_solver=locked_solver,
                capability_tags=source_tags,
                source_provider=source_provider,
                selected_provider=None,
                candidates_considered=0,
            ),
        )

    selected = sorted(
        candidates,
        key=lambda row: _candidate_sort_key(
            row,
            locked_kind=locked_kind,
            locked_version=locked_version,
        ),
    )[0]
    selected_model_version = selected.model_version
    return ProviderMigrationResult(
        status=ProviderMigrationStatus.MIGRATED,
        selected_model_version=selected_model_version,
        response_metadata=_migration_metadata(
            status=ProviderMigrationStatus.MIGRATED,
            reason="locked provider required migration; selected active equivalent provider",
            task_type=task_type,
            locked_solver=locked_solver,
            capability_tags=source_tags,
            source_provider=source_provider,
            selected_provider=_safe_provider_metadata(
                model_version=selected_model_version,
                status=selected.lifecycle_status,
            ),
            candidates_considered=len(candidates),
        ),
    )
