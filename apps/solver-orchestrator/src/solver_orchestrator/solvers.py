"""HiGHS LP solver wrapper (Story 3.1).

CRG2: cold-start vs warm-start distinction + HiGHS pre-warm.
- Cold-start P95 < 5s (first call after process startup; HiGHS lib load)
- Warm-start P95 < 200ms (subsequent calls; HiGHS already loaded + thread-pool warm)
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from itertools import combinations
from typing import Any

import highspy
import numpy as np

TOP_K_STRATEGY = "lp_vertex_enumeration_v1"
MAX_TOP_K_VERTEX_VARIABLES = 8
MAX_TOP_K_VERTEX_COMBINATIONS = 10_000
TOP_K_FEASIBILITY_TOLERANCE = 1e-7
TOP_K_DEDUPE_DECIMALS = 7


@dataclass(frozen=True)
class LPSolveResult:
    """LP solve outcome."""

    status: str  # 'optimal' / 'infeasible' / 'unbounded' / 'timeout' / 'error'
    objective: float | None
    solution: dict[str, list[float]] | None  # {"x": [...]}
    solve_seconds: float
    error_field_path: str | None = None
    error_constraint: str | None = None
    alternatives: list[dict[str, Any]] | None = None


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


def _timeout_result_from_highs(
    highs: Any,
    *,
    num_columns: int,
    elapsed: float,
    max_solve_seconds: float,
) -> LPSolveResult:
    """Build a timeout result, preserving a finite incumbent if HiGHS has one."""
    solution: dict[str, list[float]] | None = None
    objective: float | None = None
    try:
        raw_solution = highs.getSolution()
        x_values = [float(value) for value in list(raw_solution.col_value)]
        if len(x_values) == num_columns and all(math.isfinite(value) for value in x_values):
            solution = {"x": x_values}
    except Exception:
        solution = None

    try:
        raw_objective = float(highs.getInfo().objective_function_value)
        if math.isfinite(raw_objective):
            objective = raw_objective
    except Exception:
        objective = None

    return LPSolveResult(
        status="timeout",
        objective=objective,
        solution=solution,
        solve_seconds=elapsed,
        error_field_path="options.max_solve_seconds",
        error_constraint=f"solver timed out after {max_solve_seconds}s",
    )


def _finite_float_list(values: list[float] | None, *, fallback: list[float]) -> list[float]:
    if values is None:
        return list(fallback)
    return [float(value) for value in values]


def _objective_value(c: list[float], x_values: list[float]) -> float:
    return float(sum(float(cost) * float(value) for cost, value in zip(c, x_values, strict=True)))


def _solution_key(x_values: list[float]) -> tuple[float, ...]:
    return tuple(round(float(value), TOP_K_DEDUPE_DECIMALS) for value in x_values)


def _is_feasible_candidate(
    x_values: list[float],
    *,
    a_constraints: list[list[float]],
    b_rhs: list[float],
    x_lower: list[float],
    x_upper: list[float],
) -> bool:
    if not all(math.isfinite(value) for value in x_values):
        return False
    for value, lower, upper in zip(x_values, x_lower, x_upper, strict=True):
        if value < lower - TOP_K_FEASIBILITY_TOLERANCE:
            return False
        if math.isfinite(upper) and value > upper + TOP_K_FEASIBILITY_TOLERANCE:
            return False
    for row, rhs in zip(a_constraints, b_rhs, strict=True):
        lhs = sum(float(coef) * value for coef, value in zip(row, x_values, strict=True))
        if lhs > float(rhs) + TOP_K_FEASIBILITY_TOLERANCE:
            return False
    return True


def _candidate_payload(
    *,
    rank: int,
    score: float,
    objective: float,
    x_values: list[float],
    source: str,
) -> dict[str, Any]:
    return {
        "rank": rank,
        "score": float(score),
        "objective": float(objective),
        "solution": {"x": [float(value) for value in x_values]},
        "source": source,
    }


def _score_objective(
    *,
    candidate_objective: float,
    best_objective: float,
    sense: str,
    is_primary: bool,
) -> float:
    if is_primary:
        return 1.0
    normalizer = max(abs(best_objective), 1.0)
    if sense == "maximize":
        relative_gap = max(0.0, best_objective - candidate_objective) / normalizer
    else:
        relative_gap = max(0.0, candidate_objective - best_objective) / normalizer
    return float(1.0 / (1.0 + relative_gap))


def _sort_candidate_tuple(
    item: tuple[list[float], float],
    *,
    sense: str,
) -> tuple[float, tuple[float, ...]]:
    x_values, objective = item
    sortable_objective = -objective if sense == "maximize" else objective
    return (sortable_objective, tuple(x_values))


def _lp_top_k_alternatives(
    *,
    c: list[float],
    a_constraints: list[list[float]],
    b_rhs: list[float],
    x_lower: list[float] | None,
    x_upper: list[float] | None,
    sense: str,
    primary_solution: dict[str, list[float]] | None,
    primary_objective: float | None,
    top_k_alternatives: int,
) -> list[dict[str, Any]] | None:
    """Return deterministic feasible LP vertex alternatives for small bounded LPs."""
    if top_k_alternatives <= 1 or primary_solution is None or primary_objective is None:
        return None
    primary_x = [float(value) for value in primary_solution.get("x", [])]
    n = len(c)
    if len(primary_x) != n or not all(math.isfinite(value) for value in primary_x):
        return None
    if not math.isfinite(float(primary_objective)):
        return None
    if n == 0 or n > MAX_TOP_K_VERTEX_VARIABLES:
        return [
            _candidate_payload(
                rank=1,
                score=1.0,
                objective=float(primary_objective),
                x_values=primary_x,
                source="primary",
            )
        ]

    lower_bounds = _finite_float_list(x_lower, fallback=[0.0] * n)
    upper_bounds = _finite_float_list(x_upper, fallback=[highspy.kHighsInf] * n)

    candidates_by_key: dict[tuple[float, ...], tuple[list[float], float]] = {}
    primary_key = _solution_key(primary_x)
    candidates_by_key[primary_key] = (primary_x, float(primary_objective))

    active_rows: list[tuple[list[float], float]] = []
    for row, rhs in zip(a_constraints, b_rhs, strict=True):
        active_rows.append(([float(value) for value in row], float(rhs)))
    for idx, lower in enumerate(lower_bounds):
        row = [0.0] * n
        row[idx] = 1.0
        active_rows.append((row, float(lower)))
    for idx, upper in enumerate(upper_bounds):
        if not math.isfinite(upper):
            continue
        row = [0.0] * n
        row[idx] = 1.0
        active_rows.append((row, float(upper)))

    combination_count = 0
    for selected_rows in combinations(active_rows, n):
        combination_count += 1
        if combination_count > MAX_TOP_K_VERTEX_COMBINATIONS:
            break
        matrix = np.array([row for row, _row_rhs in selected_rows], dtype=float)
        active_rhs = np.array([row_rhs for _row, row_rhs in selected_rows], dtype=float)
        try:
            solution = np.linalg.solve(matrix, active_rhs)
        except np.linalg.LinAlgError:
            continue
        x_values = [float(value) for value in solution.tolist()]
        if not _is_feasible_candidate(
            x_values,
            a_constraints=a_constraints,
            b_rhs=b_rhs,
            x_lower=lower_bounds,
            x_upper=upper_bounds,
        ):
            continue
        objective = _objective_value(c, x_values)
        if not math.isfinite(objective):
            continue
        key = _solution_key(x_values)
        candidates_by_key.setdefault(key, (x_values, objective))

    primary_candidate = candidates_by_key.pop(primary_key, (primary_x, float(primary_objective)))
    sorted_candidates = sorted(
        candidates_by_key.values(),
        key=lambda item: _sort_candidate_tuple(item, sense=sense),
    )
    ranked_candidates = [primary_candidate, *sorted_candidates][:top_k_alternatives]
    best_objective = float(primary_objective)
    alternatives: list[dict[str, Any]] = []
    for idx, (x_values, objective) in enumerate(ranked_candidates, start=1):
        is_primary = idx == 1
        alternatives.append(
            _candidate_payload(
                rank=idx,
                score=_score_objective(
                    candidate_objective=objective,
                    best_objective=best_objective,
                    sense=sense,
                    is_primary=is_primary,
                ),
                objective=objective,
                x_values=x_values,
                source="primary" if is_primary else TOP_K_STRATEGY,
            )
        )
    return alternatives


def solve_lp(
    c: list[float],
    a_constraints: list[list[float]],
    b_rhs: list[float],
    x_lower: list[float] | None = None,
    x_upper: list[float] | None = None,
    sense: str = "minimize",
    max_solve_seconds: float = 30.0,
    top_k_alternatives: int = 1,
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
        x_values = [float(value) for value in list(sol.col_value)]
        info = h.getInfo()
        objective = float(info.objective_function_value)
        solution = {"x": x_values}
        alternatives: list[dict[str, Any]] | None = None
        if top_k_alternatives > 1:
            try:
                alternatives = _lp_top_k_alternatives(
                    c=c,
                    a_constraints=a_constraints,
                    b_rhs=b_rhs,
                    x_lower=x_lower,
                    x_upper=x_upper,
                    sense=sense,
                    primary_solution=solution,
                    primary_objective=objective,
                    top_k_alternatives=top_k_alternatives,
                )
            except Exception:
                alternatives = [
                    _candidate_payload(
                        rank=1,
                        score=1.0,
                        objective=objective,
                        x_values=x_values,
                        source="primary",
                    )
                ]
        elapsed = time.perf_counter() - t0
        return LPSolveResult(
            status="optimal",
            objective=objective,
            solution=solution,
            solve_seconds=elapsed,
            alternatives=alternatives,
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
        return _timeout_result_from_highs(
            h,
            num_columns=n,
            elapsed=elapsed,
            max_solve_seconds=max_solve_seconds,
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
        options = payload.get("options") or {}
        try:
            top_k_alternatives = int(options.get("top_k_alternatives", 1))
        except (TypeError, ValueError) as e:
            return LPSolveResult(
                status="error",
                objective=None,
                solution=None,
                solve_seconds=0.0,
                error_field_path="options.top_k_alternatives",
                error_constraint=f"top_k_alternatives must be an integer: {e}",
            )
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
        top_k_alternatives=top_k_alternatives,
    )
