"""Pure equivalent matching helper tests."""

from __future__ import annotations

from capability_registry.equivalent_matching import (
    EquivalentCapabilitySnapshot,
    match_equivalent_capabilities,
)


def snapshot(
    *,
    k_algo: str,
    provider_id: str,
    version: str,
    precision: object | None = None,
    provider_kind: str = "open_source",
    provider_status: str | None = "active",
    capability_status: str = "v1",
    tags: tuple[str, ...] = ("lp",),
    supported_solvers: tuple[str, ...] = ("highs",),
    task_type: str = "lp",
) -> EquivalentCapabilitySnapshot:
    metadata = {} if precision is None else {"matching": {"precision": precision}}
    return EquivalentCapabilitySnapshot(
        k_algo=k_algo,
        task_type=task_type,
        provider_id=provider_id,
        provider_kind=provider_kind,
        provider_url=f"https://{provider_id}.example.com/",
        provider_status=provider_status,
        model_version=version,
        capability_status=capability_status,
        supported_solvers=supported_solvers,
        tags=tags,
        metadata=metadata,
        scope_source="global",
    )


def test_match_equivalent_capabilities_ranks_precision_before_version() -> None:
    source = snapshot(k_algo="source-lp", provider_id="source", version="1.9.0")
    high_precision_far_version = snapshot(
        k_algo="high-precision",
        provider_id="commercial",
        version="3.0.0",
        precision=0.99,
        provider_kind="commercial",
    )
    lower_precision_near_version = snapshot(
        k_algo="near-version",
        provider_id="near",
        version="1.9.1",
        precision=0.95,
    )

    result = match_equivalent_capabilities(
        source=source,
        candidates=(source, lower_precision_near_version, high_precision_far_version),
        solver="highs",
        max_results=10,
    )

    assert [candidate.snapshot.k_algo for candidate in result.candidates] == [
        "high-precision",
        "near-version",
    ]
    assert result.rejection_counts["source_excluded"] == 1


def test_match_equivalent_capabilities_uses_version_then_lexical_tie_breaks() -> None:
    source = snapshot(k_algo="source-lp", provider_id="source", version="1.9.0")
    candidates = (
        snapshot(k_algo="z-lp", provider_id="z-provider", version="1.9.1", precision=0.9),
        snapshot(k_algo="a-lp", provider_id="a-provider", version="1.9.1", precision=0.9),
        snapshot(k_algo="non-semver", provider_id="b-provider", version="release-x", precision=0.9),
        snapshot(k_algo="closer", provider_id="c-provider", version="1.9.0", precision=0.9),
    )

    result = match_equivalent_capabilities(
        source=source,
        candidates=candidates,
        solver="highs",
        max_results=10,
    )

    assert [candidate.snapshot.k_algo for candidate in result.candidates] == [
        "closer",
        "a-lp",
        "z-lp",
        "non-semver",
    ]


def test_match_equivalent_capabilities_counts_rejections_without_crashing() -> None:
    source = snapshot(k_algo="source-lp", provider_id="source", version="1.9.0")
    candidates = (
        snapshot(k_algo="wrong-task", provider_id="wrong-task", version="1.9.0", task_type="milp"),
        snapshot(
            k_algo="wrong-tags", provider_id="wrong-tags", version="1.9.0", tags=("lp", "milp")
        ),
        snapshot(
            k_algo="wrong-solver",
            provider_id="wrong-solver",
            version="1.9.0",
            supported_solvers=("cbc",),
        ),
        snapshot(
            k_algo="missing-provider", provider_id="missing", version="1.9.0", provider_status=None
        ),
        snapshot(
            k_algo="inactive", provider_id="inactive", version="1.9.0", provider_status="inactive"
        ),
        snapshot(
            k_algo="shadow", provider_id="shadow", version="1.9.0", capability_status="shadow"
        ),
        snapshot(k_algo="bad-precision", provider_id="bad", version="1.9.0", precision="excellent"),
    )

    result = match_equivalent_capabilities(
        source=source,
        candidates=candidates,
        solver="highs",
        max_results=10,
    )

    assert result.candidates == ()
    assert result.rejection_counts == {
        "source_excluded": 0,
        "task_type_mismatch": 1,
        "tag_mismatch": 1,
        "solver_mismatch": 1,
        "provider_missing": 1,
        "provider_not_active": 1,
        "capability_not_eligible": 1,
        "invalid_precision": 1,
    }
