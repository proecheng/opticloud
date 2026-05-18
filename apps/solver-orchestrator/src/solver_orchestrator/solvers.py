"""HiGHS LP solver wrapper (Story 3.1).

CRG2: cold-start vs warm-start distinction + HiGHS pre-warm.
- Cold-start P95 < 5s (first call after process startup; HiGHS lib load)
- Warm-start P95 < 200ms (subsequent calls; HiGHS already loaded + thread-pool warm)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import highspy
import numpy as np


@dataclass(frozen=True)
class LPSolveResult:
    """LP solve outcome."""

    status: str  # 'optimal' / 'infeasible' / 'unbounded' / 'timeout' / 'error'
    objective: float | None
    solution: dict[str, list[float]] | None  # {"x": [...]}
    solve_seconds: float
    error_field_path: str | None = None
    error_constraint: str | None = None


_warm = False


def prewarm() -> None:
    """CRG2: Pre-warm HiGHS at startup (load lib + warm thread pool)."""
    global _warm
    if _warm:
        return
    # Run a tiny LP to load the lib & JIT
    h = highspy.Highs()
    h.silent()
    lp = highspy.HighsLp()
    lp.num_col_ = 1
    lp.num_row_ = 0
    lp.col_cost_ = np.array([1.0])
    lp.col_lower_ = np.array([0.0])
    lp.col_upper_ = np.array([1.0])
    lp.sense_ = highspy.ObjSense.kMinimize
    h.passModel(lp)
    h.run()
    _warm = True


def solve_lp(
    c: list[float],
    a_constraints: list[list[float]],
    b_rhs: list[float],
    x_lower: list[float] | None = None,
    x_upper: list[float] | None = None,
    sense: str = "minimize",
    max_solve_seconds: float = 30.0,
) -> LPSolveResult:
    """Solve LP: min c·x s.t. A·x ≤ b, x_lower ≤ x ≤ x_upper.

    Returns LPSolveResult with status + solution + objective + timing.
    """
    t0 = time.perf_counter()
    n = len(c)
    if not a_constraints:
        return LPSolveResult(
            status="error",
            objective=None,
            solution=None,
            solve_seconds=time.perf_counter() - t0,
            error_field_path="st.A",
            error_constraint="constraint matrix A is empty",
        )
    m = len(a_constraints)
    if any(len(row) != n for row in a_constraints):
        return LPSolveResult(
            status="error",
            objective=None,
            solution=None,
            solve_seconds=time.perf_counter() - t0,
            error_field_path="st.A",
            error_constraint=f"row width must equal len(c) = {n}",
        )
    if len(b_rhs) != m:
        return LPSolveResult(
            status="error",
            objective=None,
            solution=None,
            solve_seconds=time.perf_counter() - t0,
            error_field_path="st.b",
            error_constraint=f"len(b) must equal len(A.rows) = {m}",
        )

    h = highspy.Highs()
    h.silent()
    h.setOptionValue("time_limit", float(max_solve_seconds))

    lp = highspy.HighsLp()
    lp.num_col_ = n
    lp.num_row_ = m
    lp.col_cost_ = np.array(c, dtype=float)
    lp.col_lower_ = np.array(x_lower if x_lower is not None else [0.0] * n, dtype=float)
    lp.col_upper_ = np.array(
        x_upper if x_upper is not None else [highspy.kHighsInf] * n, dtype=float
    )
    lp.row_lower_ = np.array([-highspy.kHighsInf] * m, dtype=float)
    lp.row_upper_ = np.array(b_rhs, dtype=float)
    # Build sparse column-wise representation
    a_flat: list[float] = []
    a_index: list[int] = []
    a_start: list[int] = [0]
    for j in range(n):
        for i in range(m):
            v = a_constraints[i][j]
            if v != 0:
                a_flat.append(float(v))
                a_index.append(i)
        a_start.append(len(a_flat))
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = np.array(a_start, dtype=np.int32)
    lp.a_matrix_.index_ = np.array(a_index, dtype=np.int32)
    lp.a_matrix_.value_ = np.array(a_flat, dtype=float)

    lp.sense_ = highspy.ObjSense.kMinimize if sense == "minimize" else highspy.ObjSense.kMaximize

    h.passModel(lp)
    run_status = h.run()
    elapsed = time.perf_counter() - t0

    if run_status != highspy.HighsStatus.kOk:
        return LPSolveResult(
            status="error",
            objective=None,
            solution=None,
            solve_seconds=elapsed,
            error_field_path="st",
            error_constraint=f"HiGHS error: {run_status.name}",
        )

    model_status = h.getModelStatus()

    if model_status == highspy.HighsModelStatus.kOptimal:
        sol = h.getSolution()
        x_values = list(sol.col_value)
        info = h.getInfo()
        return LPSolveResult(
            status="optimal",
            objective=float(info.objective_function_value),
            solution={"x": x_values},
            solve_seconds=elapsed,
        )

    if model_status == highspy.HighsModelStatus.kInfeasible:
        return LPSolveResult(
            status="infeasible",
            objective=None,
            solution=None,
            solve_seconds=elapsed,
            error_field_path="st",
            error_constraint="LP is infeasible (no feasible region)",
        )

    if model_status in (
        highspy.HighsModelStatus.kUnbounded,
        highspy.HighsModelStatus.kUnboundedOrInfeasible,
    ):
        return LPSolveResult(
            status="unbounded",
            objective=None,
            solution=None,
            solve_seconds=elapsed,
            error_field_path="st",
            error_constraint="LP is unbounded",
        )

    if model_status == highspy.HighsModelStatus.kTimeLimit:
        return LPSolveResult(
            status="timeout",
            objective=None,
            solution=None,
            solve_seconds=elapsed,
            error_field_path="options.max_solve_seconds",
            error_constraint=f"solver timed out after {max_solve_seconds}s",
        )

    return LPSolveResult(
        status="error",
        objective=None,
        solution=None,
        solve_seconds=elapsed,
        error_field_path="st",
        error_constraint=f"HiGHS unexpected status: {model_status.name}",
    )


def solve_from_request(payload: dict[str, Any], max_solve_seconds: float = 30.0) -> LPSolveResult:
    """Parse OptiCloud LP request payload and dispatch to solve_lp."""
    try:
        minimize = payload.get("minimize") or {}
        maximize = payload.get("maximize") or {}
        sense_obj = minimize if minimize else maximize
        sense = "minimize" if minimize else "maximize"
        c = list(sense_obj.get("c", []))
        st = payload.get("st") or {}
        a = st.get("A") or []
        b = list(st.get("b", []))
        x_lower = st.get("x_lower")
        x_upper = st.get("x_upper")
    except (TypeError, AttributeError) as e:
        return LPSolveResult(
            status="error",
            objective=None,
            solution=None,
            solve_seconds=0.0,
            error_field_path="$",
            error_constraint=f"malformed payload: {e}",
        )

    return solve_lp(
        c=c,
        a_constraints=a,
        b_rhs=b,
        x_lower=x_lower,
        x_upper=x_upper,
        sense=sense,
        max_solve_seconds=max_solve_seconds,
    )
