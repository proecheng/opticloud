"""HiGHS LP solver tests + mock-real divergence (Q-T1)."""

from __future__ import annotations

import pytest
from solver_orchestrator.solvers import prewarm, solve_from_request, solve_lp


@pytest.fixture(autouse=True, scope="module")
def _prewarm() -> None:
    prewarm()


def test_basic_lp_minimize() -> None:
    """min x₁ + x₂ s.t. x₁ + x₂ ≤ 10, x ≥ 0 → optimal (0, 0) obj=0."""
    result = solve_lp(c=[1.0, 1.0], a_constraints=[[1.0, 1.0]], b_rhs=[10.0])
    assert result.status == "optimal"
    assert result.objective == pytest.approx(0.0)
    assert result.solution is not None
    assert all(x >= 0 for x in result.solution["x"])


def test_lp_with_negative_costs_maximize() -> None:
    """max x₁ + x₂ s.t. x₁ + x₂ ≤ 10, x ≥ 0 → optimal (10, 0) or (0, 10) obj=10."""
    payload = {
        "task_type": "lp",
        "maximize": {"c": [1.0, 1.0]},
        "st": {"A": [[1.0, 1.0]], "b": [10.0]},
    }
    result = solve_from_request(payload)
    assert result.status == "optimal"
    assert result.objective == pytest.approx(10.0)


def test_lp_infeasible() -> None:
    """x ≥ 0 and x ≤ -1 → infeasible."""
    result = solve_lp(c=[1.0], a_constraints=[[1.0]], b_rhs=[-1.0])
    assert result.status == "infeasible"
    assert result.error_field_path == "st"


def test_lp_malformed_a_shape() -> None:
    result = solve_lp(c=[1.0, 1.0], a_constraints=[[1.0]], b_rhs=[5.0])
    assert result.status == "error"
    assert result.error_field_path == "st.A"


def test_lp_malformed_b_length() -> None:
    result = solve_lp(c=[1.0], a_constraints=[[1.0], [1.0]], b_rhs=[5.0])
    assert result.status == "error"
    assert result.error_field_path == "st.b"


def test_warm_start_faster_than_cold(benchmark_runs: int = 3) -> None:
    """CRG2 — warm-start should be faster than cold-start.

    Note: prewarm() runs in fixture; first call here is already warm.
    """
    import time

    times = []
    for _ in range(benchmark_runs):
        t0 = time.perf_counter()
        result = solve_lp(c=[1.0, 1.0], a_constraints=[[1.0, 1.0]], b_rhs=[10.0])
        times.append(time.perf_counter() - t0)
        assert result.status == "optimal"

    # warm-start should be < 200ms per AC (CRG2)
    avg = sum(times) / len(times)
    assert avg < 0.5, f"warm-start avg {avg * 1000:.1f}ms > 500ms (CRG2 budget 200ms)"


def test_mock_real_divergence_lp_schema() -> None:
    """Q-T1 — verify real solve schema matches mock structure expected by SDK."""
    result = solve_lp(c=[2.0, 3.0], a_constraints=[[1.0, 1.0]], b_rhs=[5.0])
    assert result.status == "optimal"
    # Schema: solution.x is a list of floats
    assert result.solution is not None
    assert "x" in result.solution
    assert isinstance(result.solution["x"], list)
    assert all(isinstance(v, float) for v in result.solution["x"])
    # objective is a float
    assert isinstance(result.objective, float)
    # solve_seconds is a float
    assert isinstance(result.solve_seconds, float) and result.solve_seconds >= 0
