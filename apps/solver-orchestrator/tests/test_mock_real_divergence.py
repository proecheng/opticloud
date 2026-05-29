"""Story 3.14 - mock-real divergence contract tests."""

from __future__ import annotations

import json
import uuid
from collections import OrderedDict
from dataclasses import fields
from datetime import UTC, datetime

from hypothesis import given, settings
from opticloud_shared.property_test_base.strategies import lp_inputs
from solver_orchestrator import solvers
from solver_orchestrator.models import Optimization
from solver_orchestrator.routes import _build_response_content, _build_success_response

SOLVER_CONTRACT_KEYS = [
    "status",
    "objective",
    "solution",
    "solve_seconds",
    "error_field_path",
    "error_constraint",
    "alternatives",
]
ALLOWED_SOLVER_STATUSES = {"optimal", "infeasible", "unbounded", "timeout", "error"}
COMPLETED_RESPONSE_KEYS = [
    "optimization_id",
    "status",
    "solution",
    "objective",
    "model_version",
    "solve_seconds",
    "created_at",
    "completed_at",
    "citation",
    "ip_attribution",
    "progress_pct",
    "eta_seconds",
]
MODEL_VERSION_KEYS = ["provider_id", "kind", "version", "provider_url"]
ALTERNATIVE_KEYS = ["rank", "score", "objective", "solution", "source"]

MODEL_VERSION = {
    "provider_id": "highs",
    "kind": "open_source",
    "version": "1.7.0",
    "provider_url": "https://highs.dev/",
}


def _mock_solver_contract(payload: dict[str, object]) -> dict[str, object]:
    c = ((payload.get("minimize") or {}) or (payload.get("maximize") or {})).get("c", [])
    width = len(c) if isinstance(c, list) else 0
    return OrderedDict(
        [
            ("status", "optimal"),
            ("objective", 0.0),
            ("solution", {"x": [0.0] * width}),
            ("solve_seconds", 0.0),
            ("error_field_path", None),
            ("error_constraint", None),
            ("alternatives", None),
        ]
    )


def _result_contract(result: solvers.LPSolveResult) -> dict[str, object]:
    return OrderedDict(
        [
            ("status", result.status),
            ("objective", result.objective),
            ("solution", result.solution),
            ("solve_seconds", result.solve_seconds),
            ("error_field_path", result.error_field_path),
            ("error_constraint", result.error_constraint),
            ("alternatives", result.alternatives),
        ]
    )


def _assert_solution_contract(solution: object) -> None:
    if solution is None:
        return
    assert isinstance(solution, dict)
    assert list(solution.keys()) == ["x"]
    x_values = solution["x"]
    assert isinstance(x_values, list)
    assert all(isinstance(value, float) for value in x_values)


def _assert_alternatives_contract(alternatives: object) -> None:
    if alternatives is None:
        return
    assert isinstance(alternatives, list)
    for alternative in alternatives:
        assert isinstance(alternative, dict)
        assert list(alternative.keys()) == ALTERNATIVE_KEYS
        assert isinstance(alternative["rank"], int)
        assert isinstance(alternative["score"], float)
        assert isinstance(alternative["objective"], float)
        assert isinstance(alternative["source"], str)
        _assert_solution_contract(alternative["solution"])


def _assert_solver_contract(contract: dict[str, object]) -> None:
    assert list(contract.keys()) == SOLVER_CONTRACT_KEYS
    assert contract["status"] in ALLOWED_SOLVER_STATUSES
    assert contract["objective"] is None or isinstance(contract["objective"], float)
    assert isinstance(contract["solve_seconds"], float)
    assert contract["solve_seconds"] >= 0
    assert contract["error_field_path"] is None or isinstance(contract["error_field_path"], str)
    assert contract["error_constraint"] is None or isinstance(contract["error_constraint"], str)
    _assert_solution_contract(contract["solution"])
    _assert_alternatives_contract(contract["alternatives"])


def _assert_model_version_contract(model_version: object) -> None:
    assert isinstance(model_version, dict)
    assert list(model_version.keys()) == MODEL_VERSION_KEYS
    assert model_version["provider_id"] == "highs"
    assert model_version["kind"] == "open_source"
    assert model_version["provider_url"] == "https://highs.dev/"
    assert "provider_kind" not in model_version


def _assert_no_internal_leaks(content: dict[str, object]) -> None:
    serialized = json.dumps(content)
    assert "_system" not in serialized
    assert "provider_route" not in serialized
    assert "billing" not in serialized
    assert "billing_charge_id" not in serialized
    assert "api_key" not in serialized
    assert "authorization" not in serialized
    assert "sk-" not in serialized


def _make_completed_optimization(
    *,
    solution: dict[str, list[float]] | None = None,
    objective: float | None = None,
    input_payload: dict[str, object] | None = None,
) -> Optimization:
    now = datetime.now(UTC)
    opt = Optimization(
        user_id=uuid.uuid4(),
        api_key_id=uuid.uuid4(),
        task_type="lp",
        status="completed",
        input_payload=input_payload or {"task_type": "lp"},
        solution=solution if solution is not None else {"x": [0.0, 0.0]},
        objective=objective if objective is not None else 0.0,
        model_version=dict(MODEL_VERSION),
        solve_seconds=0.01,
        created_at=now,
        completed_at=now,
    )
    opt.id = uuid.uuid4()
    return opt


@given(payload=lp_inputs(n_max=4, m_max=4))
@settings(max_examples=40, deadline=2000)
def test_property_lp_mock_and_real_solver_result_schema_order(payload: dict[str, object]) -> None:
    mock_contract = _mock_solver_contract(payload)
    real_contract = _result_contract(solvers.solve_from_request(payload))

    _assert_solver_contract(mock_contract)
    _assert_solver_contract(real_contract)
    assert list(real_contract.keys()) == list(mock_contract.keys())


def test_lp_solve_result_dataclass_order_matches_mock_contract() -> None:
    assert [field.name for field in fields(solvers.LPSolveResult)] == SOLVER_CONTRACT_KEYS


def test_solver_terminal_result_contracts_cover_success_error_timeout_unbounded() -> None:
    cases = [
        solvers.solve_lp(c=[1.0, 1.0], a_constraints=[[1.0, 1.0]], b_rhs=[5.0]),
        solvers.solve_lp(c=[1.0], a_constraints=[[1.0]], b_rhs=[-1.0]),
        solvers.solve_lp(c=[1.0, 1.0], a_constraints=[[1.0]], b_rhs=[5.0]),
        solvers.LPSolveResult(
            status="timeout",
            objective=None,
            solution=None,
            solve_seconds=0.25,
            error_field_path="options.max_solve_seconds",
            error_constraint="solver timed out after 0.25s",
        ),
        solvers.LPSolveResult(
            status="unbounded",
            objective=None,
            solution=None,
            solve_seconds=0.01,
            error_field_path="st",
            error_constraint="LP is unbounded",
        ),
    ]

    assert [case.status for case in cases] == [
        "optimal",
        "infeasible",
        "error",
        "timeout",
        "unbounded",
    ]
    for result in cases:
        _assert_solver_contract(_result_contract(result))


def test_top_k_alternatives_contract_preserves_order_and_shape() -> None:
    result = solvers.solve_lp(
        c=[1.0, 1.0, 1.0],
        a_constraints=[[1.0, 1.0, 1.0]],
        b_rhs=[10.0],
        sense="maximize",
        top_k_alternatives=3,
    )

    assert result.status == "optimal"
    contract = _result_contract(result)
    _assert_solver_contract(contract)
    alternatives = contract["alternatives"]
    assert isinstance(alternatives, list)
    assert [item["rank"] for item in alternatives] == [1, 2, 3]
    assert alternatives[0]["solution"] == contract["solution"]


def test_completed_response_contract_preserves_public_key_order_and_model_version() -> None:
    opt = _make_completed_optimization(
        input_payload={
            "task_type": "lp",
            "_system": {
                "provider_route": {"provider_id": "highs"},
                "billing": {"billing_charge_id": "charge-secret"},
            },
        }
    )

    content = _build_response_content(opt)

    assert list(content.keys())[: len(COMPLETED_RESPONSE_KEYS)] == COMPLETED_RESPONSE_KEYS
    _assert_solution_contract(content["solution"])
    _assert_model_version_contract(content["model_version"])
    assert content["status"] == "completed"
    assert content["progress_pct"] == 100
    assert content["eta_seconds"] == 0
    _assert_no_internal_leaks(content)


def test_success_response_json_roundtrip_preserves_contract_order() -> None:
    opt = _make_completed_optimization()

    response = _build_success_response(opt)
    body = json.loads(response.body)

    assert response.status_code == 200
    assert list(body.keys())[: len(COMPLETED_RESPONSE_KEYS)] == COMPLETED_RESPONSE_KEYS
    _assert_model_version_contract(body["model_version"])
    _assert_no_internal_leaks(body)


def test_completed_response_includes_top_k_metadata_contract_when_present() -> None:
    alternatives = [
        {
            "rank": 1,
            "score": 1.0,
            "objective": 10.0,
            "solution": {"x": [10.0, 0.0]},
            "source": "primary",
        },
        {
            "rank": 2,
            "score": 0.5,
            "objective": 5.0,
            "solution": {"x": [5.0, 0.0]},
            "source": solvers.TOP_K_STRATEGY,
        },
    ]
    opt = _make_completed_optimization(
        solution={"x": [10.0, 0.0]},
        objective=10.0,
        input_payload={
            "task_type": "lp",
            "_system": {
                "top_k_alternatives": {
                    "strategy": solvers.TOP_K_STRATEGY,
                    "requested": 2,
                    "returned": 2,
                    "alternatives": alternatives,
                }
            },
        },
    )

    content = _build_response_content(opt)

    assert content["top_k_alternatives_requested"] == 2
    assert content["top_k_alternatives_returned"] == 2
    assert content["alternatives"] == alternatives
    _assert_alternatives_contract(content["alternatives"])
    _assert_no_internal_leaks(content)
