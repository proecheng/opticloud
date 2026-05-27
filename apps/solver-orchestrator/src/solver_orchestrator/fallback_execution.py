"""Story 2.7 - fallback attempt planning and metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from solver_orchestrator import solvers
from solver_orchestrator.provider_routing import (
    ProviderRouteMetadata,
    ProviderRouteResult,
    ProviderRouteStatus,
    provider_route_to_system_metadata,
    select_provider_route,
)

AttemptRole = Literal["primary", "fallback"]


class FallbackPlanStatus(StrEnum):
    OK = "ok"
    INVALID_FALLBACK_SOLVER = "invalid_fallback_solver"


@dataclass(frozen=True)
class FallbackAttempt:
    attempt: int
    role: AttemptRole
    requested_solver: str | None
    route: ProviderRouteResult
    fallback_chain_index: int | None = None


@dataclass(frozen=True)
class FallbackAttemptPlan:
    status: FallbackPlanStatus
    attempts: list[FallbackAttempt]
    invalid_candidate: str | None = None
    invalid_index: int | None = None
    supported_solvers: list[str] | None = None


def build_fallback_attempts(
    *,
    primary_route: ProviderRouteResult,
    task_type: str,
    requested_solver: str | None,
    fallback_chain: list[str] | None,
) -> FallbackAttemptPlan:
    """Build an ordered primary + fallback attempt plan."""
    attempts = [
        FallbackAttempt(
            attempt=1,
            role="primary",
            requested_solver=requested_solver,
            route=primary_route,
        )
    ]
    for idx, candidate in enumerate((fallback_chain or [])[:3]):
        route = select_provider_route(task_type, candidate)
        if route.status is not ProviderRouteStatus.OK:
            return FallbackAttemptPlan(
                status=FallbackPlanStatus.INVALID_FALLBACK_SOLVER,
                attempts=attempts,
                invalid_candidate=candidate,
                invalid_index=idx,
                supported_solvers=list(route.supported_solvers),
            )
        attempts.append(
            FallbackAttempt(
                attempt=len(attempts) + 1,
                role="fallback",
                requested_solver=candidate,
                route=route,
                fallback_chain_index=idx,
            )
        )
    return FallbackAttemptPlan(status=FallbackPlanStatus.OK, attempts=attempts)


def is_retryable_solver_result(result: solvers.LPSolveResult) -> bool:
    """Return true for infrastructure/provider style failures that may fall back."""
    return result.status in {"timeout", "error"}


def attempt_route_metadata(attempt: FallbackAttempt, *, task_type: str) -> ProviderRouteMetadata:
    return provider_route_to_system_metadata(
        attempt.route,
        task_type=task_type,
        requested_solver=attempt.requested_solver,
    )


def fallback_attempt_to_metadata(
    attempt: FallbackAttempt,
    result: solvers.LPSolveResult,
    *,
    task_type: str,
    retryable: bool,
) -> dict[str, object]:
    """Return bounded internal attempt metadata for persistence."""
    route_metadata = attempt_route_metadata(attempt, task_type=task_type)
    metadata: dict[str, object] = {
        "attempt": attempt.attempt,
        "role": attempt.role,
        "requested_solver": attempt.requested_solver,
        "selected_solver": route_metadata["selected_solver"],
        "provider_id": route_metadata["provider_id"],
        "provider_kind": route_metadata["provider_kind"],
        "provider_url": route_metadata["provider_url"],
        "routing_reason": route_metadata["routing_reason"],
        "status": result.status,
        "retryable": retryable,
        "solve_seconds": result.solve_seconds,
    }
    if result.error_field_path is not None:
        metadata["error_field_path"] = str(result.error_field_path)
    if result.error_constraint is not None:
        metadata["error_constraint"] = str(result.error_constraint)[:500]
    return metadata


def build_fallback_execution_metadata(
    *,
    attempt_metadata: list[dict[str, object]],
    terminal_result: solvers.LPSolveResult,
    terminal_attempt: FallbackAttempt,
    total_solve_seconds: float,
    max_fallback_retries: int,
    exhausted: bool,
) -> dict[str, object]:
    return {
        "max_fallback_retries": max_fallback_retries,
        "attempts": attempt_metadata,
        "terminal_status": terminal_result.status,
        "terminal_attempt": terminal_attempt.attempt,
        "exhausted": exhausted,
        "solve_seconds": total_solve_seconds,
    }
