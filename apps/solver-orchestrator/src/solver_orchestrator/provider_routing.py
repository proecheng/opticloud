"""Story 2.6 — provider routing for solver-orchestrator."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypedDict

from solver_orchestrator.catalog import (
    Algorithm,
    find_by_task_type_and_solver,
    self_audit_missing_rules,
    self_audit_passed,
    self_audit_ticket_id,
)


class ProviderRouteStatus(StrEnum):
    OK = "ok"
    UNSUPPORTED_TASK_TYPE = "unsupported_task_type"
    UNSUPPORTED_SOLVER = "unsupported_solver"
    UNAUDITED_SELF_ALGORITHM = "unaudited_self_algorithm"


class ProviderRouteMetadata(TypedDict):
    task_type: str
    requested_solver: str | None
    selected_solver: str
    provider_id: str
    provider_kind: str
    provider_url: str
    routing_reason: str


@dataclass(frozen=True)
class ProviderRouteResult:
    status: ProviderRouteStatus
    algorithm: Algorithm | None
    selected_solver: str | None
    model_version: dict[str, Any]
    supported_solvers: list[str]
    provider_kind: str | None
    routing_reason: str
    blocked_k_algo: str | None = None
    blocked_provider_id: str | None = None
    audit_ticket_id: str | None = None
    missing_self_audit_rules: list[str] | None = None


def select_provider_route(task_type: str, solver: str | None) -> ProviderRouteResult:
    """Resolve the provider route for a task type and optional solver."""
    algorithm, supported_solvers = find_by_task_type_and_solver(task_type, solver)
    if algorithm is None and not supported_solvers:
        return ProviderRouteResult(
            status=ProviderRouteStatus.UNSUPPORTED_TASK_TYPE,
            algorithm=None,
            selected_solver=None,
            model_version={},
            supported_solvers=[],
            provider_kind=None,
            routing_reason="unknown_task_type",
        )
    if algorithm is None:
        return ProviderRouteResult(
            status=ProviderRouteStatus.UNSUPPORTED_SOLVER,
            algorithm=None,
            selected_solver=None,
            model_version={},
            supported_solvers=list(supported_solvers),
            provider_kind=None,
            routing_reason="unsupported_solver",
        )

    algorithm_copy = deepcopy(algorithm)
    if not self_audit_passed(algorithm_copy):
        provider_id = str(algorithm_copy["model_version"]["provider_id"])
        return ProviderRouteResult(
            status=ProviderRouteStatus.UNAUDITED_SELF_ALGORITHM,
            algorithm=None,
            selected_solver=None,
            model_version={},
            supported_solvers=list(supported_solvers),
            provider_kind="self",
            routing_reason="unaudited_self_algorithm",
            blocked_k_algo=str(algorithm_copy["k_algo"]),
            blocked_provider_id=provider_id,
            audit_ticket_id=self_audit_ticket_id(str(algorithm_copy["k_algo"]), provider_id),
            missing_self_audit_rules=self_audit_missing_rules(algorithm_copy),
        )

    selected_solver = solver if solver is not None else algorithm_copy["supported_solvers"][0]
    model_version = dict(algorithm_copy["model_version"])
    provider_kind = str(model_version["kind"])
    routing_reason = "explicit_solver" if solver is not None else "default_solver"
    return ProviderRouteResult(
        status=ProviderRouteStatus.OK,
        algorithm=algorithm_copy,
        selected_solver=selected_solver,
        model_version=model_version,
        supported_solvers=list(supported_solvers),
        provider_kind=provider_kind,
        routing_reason=routing_reason,
    )


def provider_route_to_system_metadata(
    route: ProviderRouteResult,
    *,
    task_type: str,
    requested_solver: str | None,
) -> ProviderRouteMetadata:
    """Convert a route to namespaced system metadata."""
    if (
        route.status is not ProviderRouteStatus.OK
        or route.algorithm is None
        or route.selected_solver is None
    ):
        raise ValueError("provider route metadata requires a successful route")

    return {
        "task_type": task_type,
        "requested_solver": requested_solver,
        "selected_solver": route.selected_solver,
        "provider_id": str(route.model_version["provider_id"]),
        "provider_kind": str(route.model_version["kind"]),
        "provider_url": str(route.model_version["provider_url"]),
        "routing_reason": route.routing_reason,
    }
