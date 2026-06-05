"""Story 6.C.1 - provider migration resolver tests."""

from __future__ import annotations

from solver_orchestrator.provider_migration import (
    ProviderCapabilitySnapshot,
    ProviderLifecycleStatus,
    ProviderMigrationStatus,
    build_catalog_provider_snapshot,
    resolve_provider_migration,
)


def _row(
    *,
    provider_id: str,
    version: str,
    status: ProviderLifecycleStatus = "active",
    kind: str = "open_source",
    k_algo: str | None = None,
    task_type: str = "lp",
    tags: tuple[str, ...] = ("lp", "linear_programming"),
    supported_solvers: tuple[str, ...] = ("highs",),
) -> ProviderCapabilitySnapshot:
    return ProviderCapabilitySnapshot(
        k_algo=k_algo or f"{provider_id}-lp",
        task_type=task_type,
        provider_id=provider_id,
        provider_kind=kind,
        provider_url=f"https://providers.example/{provider_id}",
        version=version,
        lifecycle_status=status,
        supported_solvers=supported_solvers,
        capability_tags=tags,
    )


def test_active_locked_provider_does_not_migrate() -> None:
    locked_model = {
        "provider_id": "highs",
        "kind": "open_source",
        "version": "1.7.0",
        "provider_url": "https://highs.dev/",
    }

    result = resolve_provider_migration(
        locked_model_version=locked_model,
        task_type="lp",
        locked_solver="highs",
        snapshot=[_row(provider_id="highs", version="1.7.0")],
    )

    assert result.status is ProviderMigrationStatus.NOT_REQUIRED
    assert result.selected_model_version == locked_model
    assert result.response_metadata is None


def test_deprecated_locked_provider_migrates_to_active_equivalent() -> None:
    result = resolve_provider_migration(
        locked_model_version={
            "provider_id": "legacy-highs",
            "kind": "open_source",
            "version": "1.7.0",
            "provider_url": "https://legacy.example/highs",
        },
        task_type="lp",
        locked_solver="highs",
        snapshot=[
            _row(provider_id="legacy-highs", version="1.7.0", status="deprecated"),
            _row(provider_id="highs-active", version="1.7.1"),
        ],
    )

    assert result.status is ProviderMigrationStatus.MIGRATED
    assert result.selected_model_version == {
        "provider_id": "highs-active",
        "kind": "open_source",
        "version": "1.7.1",
        "provider_url": "https://providers.example/highs-active",
    }
    assert result.response_metadata is not None
    assert result.response_metadata["status"] == "migrated"
    assert result.response_metadata["source_provider"]["provider_id"] == "legacy-highs"
    assert result.response_metadata["selected_provider"]["provider_id"] == "highs-active"
    assert result.response_metadata["capability_tags"] == ["linear_programming", "lp"]


def test_no_equivalent_rejects_unrelated_tags_and_records_safe_metadata() -> None:
    result = resolve_provider_migration(
        locked_model_version={
            "provider_id": "legacy-highs",
            "kind": "open_source",
            "version": "1.7.0",
            "provider_url": "https://legacy.example/highs",
        },
        task_type="lp",
        locked_solver="highs",
        snapshot=[
            _row(provider_id="legacy-highs", version="1.7.0", status="retired"),
            _row(
                provider_id="vrp-provider",
                version="1.0.0",
                task_type="vrptw",
                tags=("vrptw", "time_windows"),
                supported_solvers=("or-tools",),
            ),
        ],
    )

    assert result.status is ProviderMigrationStatus.NO_EQUIVALENT
    assert result.selected_model_version is None
    assert result.response_metadata is not None
    assert result.response_metadata["status"] == "no_equivalent"
    assert result.response_metadata["source_provider"]["provider_id"] == "legacy-highs"
    assert result.response_metadata["candidates_considered"] == 0


def test_missing_source_provider_uses_task_capability_tags_for_equivalent_match() -> None:
    result = resolve_provider_migration(
        locked_model_version={
            "provider_id": "removed-highs",
            "kind": "open_source",
            "version": "1.7.0",
            "provider_url": "https://removed.example/highs",
        },
        task_type="lp",
        locked_solver="highs",
        snapshot=[
            _row(provider_id="replacement-highs", version="1.7.1"),
        ],
    )

    assert result.status is ProviderMigrationStatus.MIGRATED
    assert result.selected_model_version is not None
    assert result.selected_model_version["provider_id"] == "replacement-highs"
    assert result.response_metadata is not None
    assert result.response_metadata["source_provider"]["status"] == "unavailable"


def test_candidate_must_be_active_and_support_locked_solver() -> None:
    result = resolve_provider_migration(
        locked_model_version={
            "provider_id": "legacy-highs",
            "kind": "open_source",
            "version": "1.7.0",
            "provider_url": "https://legacy.example/highs",
        },
        task_type="lp",
        locked_solver="highs",
        snapshot=[
            _row(provider_id="legacy-highs", version="1.7.0", status="unavailable"),
            _row(provider_id="inactive-highs", version="1.7.1", status="inactive"),
            _row(
                provider_id="wrong-solver",
                version="1.7.2",
                supported_solvers=("custom-lp",),
            ),
        ],
    )

    assert result.status is ProviderMigrationStatus.NO_EQUIVALENT
    assert result.response_metadata is not None
    assert result.response_metadata["candidates_considered"] == 0


def test_ranking_prefers_same_kind_then_semver_then_lexical_tie_breaks() -> None:
    locked_model = {
        "provider_id": "legacy-highs",
        "kind": "open_source",
        "version": "1.7.0",
        "provider_url": "https://legacy.example/highs",
    }

    result = resolve_provider_migration(
        locked_model_version=locked_model,
        task_type="lp",
        locked_solver="highs",
        snapshot=[
            _row(provider_id="legacy-highs", version="1.7.0", status="exiting"),
            _row(provider_id="external-close", version="1.7.0", kind="external"),
            _row(provider_id="z-open-source", version="1.7.1", kind="open_source"),
            _row(provider_id="a-open-source", version="1.7.1", kind="open_source"),
            _row(provider_id="older-open-source", version="1.4.0", kind="open_source"),
        ],
    )

    assert result.status is ProviderMigrationStatus.MIGRATED
    assert result.selected_model_version is not None
    assert result.selected_model_version["provider_id"] == "a-open-source"
    assert result.response_metadata is not None
    assert result.response_metadata["candidates_considered"] == 4


def test_catalog_snapshot_contains_current_highs_lp_as_active() -> None:
    rows = build_catalog_provider_snapshot()
    highs_lp = next(row for row in rows if row.k_algo == "highs-lp")

    assert highs_lp.provider_id == "highs"
    assert highs_lp.lifecycle_status == "active"
    assert highs_lp.task_type == "lp"
    assert "highs" in highs_lp.supported_solvers
    assert set(highs_lp.capability_tags) == {"lp", "linear_programming"}
