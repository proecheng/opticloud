from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOLVER_SRC = ROOT / "apps" / "solver-orchestrator" / "src"
VALIDATOR_PATH = ROOT / "scripts" / "validate_gurobi_benchmark.py"
FIXTURE_SUITE_PATH = ROOT / "tools" / "gurobi_benchmark" / "lp_fixture_suite.json"
MANIFEST_PATH = ROOT / "tools" / "gurobi_benchmark" / "benchmark_manifest.json"
EVIDENCE_EXAMPLE_PATH = ROOT / "tools" / "gurobi_benchmark" / "evidence_manifest.example.json"
CI_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_gurobi_benchmark", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _assert_invalid(errors: list[str], expected: str) -> None:
    assert any(expected in error for error in errors), errors


def _real_evidence_from_example() -> dict[str, Any]:
    evidence = copy.deepcopy(_load_json(EVIDENCE_EXAMPLE_PATH))
    evidence["example_only"] = False
    evidence["run_id"] = "test-gurobi-benchmark-20260527"
    evidence["redaction_reviewed"] = True
    evidence["approval_status"] = "redaction_passed"
    evidence["aggregate_metrics"] = {
        "fixture_count": 30,
        "comparable_count": 30,
        "status_parity_count": 30,
        "objective_tolerance_pass_count": 30,
        "timeout_count": 0,
        "error_count": 0,
    }
    evidence["per_fixture_results"] = [
        {
            "fixture_id": f"lp-{index:03d}",
            "opticloud_highs_status": "optimal",
            "gurobi_status": "optimal",
            "opticloud_runtime_seconds": 0.01,
            "gurobi_runtime_seconds": 0.01,
            "opticloud_objective": 0.0,
            "gurobi_objective": 0.0,
            "not_available_reason": "",
            "objective_delta": 0.0,
            "primal_feasibility_residual": 0.0,
            "notes": "Synthetic test-only evidence row.",
        }
        for index in range(1, 31)
    ]
    evidence["artifacts"] = {
        key: value.replace("example-gurobi-benchmark-20260527", evidence["run_id"])
        for key, value in evidence["artifacts"].items()
    }
    return evidence


def test_committed_gurobi_benchmark_contract_validates_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "gurobi benchmark package OK" in result.stdout


def test_fixture_suite_has_exact_30_stable_synthetic_lp_fixtures() -> None:
    validator = _load_validator()
    suite = _load_json(FIXTURE_SUITE_PATH)

    assert validator.validate_fixture_suite(suite) == []
    fixtures = suite["fixtures"]
    assert len(fixtures) == 30
    assert [fixture["id"] for fixture in fixtures] == [f"lp-{index:03d}" for index in range(1, 31)]
    assert {fixture["category"] for fixture in fixtures} >= {
        "small_bounded",
        "resource_allocation",
        "blending",
        "transportation_style",
        "scheduling_style",
        "stress_scale_synthetic",
    }


def test_manifest_covers_all_required_benchmark_assets() -> None:
    manifest = _load_json(MANIFEST_PATH)

    assert manifest["story_key"] == "m4-5b-gurobi-benchmark-whitepaper"
    assert manifest["fixture_count"] == 30
    assert {asset["category"] for asset in manifest["assets"]} == {
        "fixture_suite",
        "methodology",
        "whitepaper",
        "evidence_schema",
        "operator_runbook",
    }
    paths = {asset["path"] for asset in manifest["assets"]}
    assert paths == {
        "tools/gurobi_benchmark/lp_fixture_suite.json",
        "tools/gurobi_benchmark/evidence_manifest.schema.json",
        "tools/gurobi_benchmark/evidence_manifest.example.json",
        "docs/benchmarks/gurobi-lp-benchmark-methodology.md",
        "docs/benchmarks/gurobi-lp-benchmark-whitepaper.md",
        "docs/runbooks/gurobi-lp-benchmark.md",
    }


def test_ci_path_filter_covers_gurobi_benchmark_assets() -> None:
    ci = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "gurobi_benchmark:" in ci
    for expected in (
        "docs/benchmarks/**",
        "docs/runbooks/gurobi-lp-benchmark.md",
        "tools/gurobi_benchmark/**",
        "scripts/validate_gurobi_benchmark.py",
        "tests/test_gurobi_benchmark.py",
        "reports/gurobi-benchmark/**",
        "gurobi-benchmark-validation",
        "uv run python scripts/validate_gurobi_benchmark.py",
        "uv run pytest tests/test_gurobi_benchmark.py",
    ):
        assert expected in ci


def test_validator_rejects_whitepaper_superiority_claims(tmp_path: Path) -> None:
    validator = _load_validator()
    bad_doc = tmp_path / "bad-whitepaper.md"
    bad_doc.write_text(
        "\n".join(
            [
                "---",
                "status: published",
                "claim_status: verified",
                "evidence_status: verified",
                "story_key: m4-5b-gurobi-benchmark-whitepaper",
                "---",
                "# Bad Whitepaper",
                "Verified benchmark results prove OptiCloud beats Gurobi and is faster than Gurobi.",
            ]
        ),
        encoding="utf-8",
    )

    errors = validator.validate_markdown_asset(
        root=tmp_path,
        path=Path("bad-whitepaper.md"),
        required_fields=["status", "claim_status", "evidence_status", "story_key"],
    )

    _assert_invalid(errors, "unsupported benchmark superiority claim")


def test_evidence_example_is_not_accepted_as_real_evidence() -> None:
    validator = _load_validator()
    suite = _load_json(FIXTURE_SUITE_PATH)
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)

    assert validator.validate_evidence_manifest(evidence, suite, real_evidence=False) == []
    errors = validator.validate_evidence_manifest(evidence, suite, real_evidence=True)

    _assert_invalid(errors, "real evidence must set example_only=false")


def test_real_evidence_path_validates_schema_without_running_solvers(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--evidence", str(EVIDENCE_EXAMPLE_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "real evidence must set example_only=false" in result.stderr

    evidence = _real_evidence_from_example()
    run_dir = tmp_path / "reports" / "gurobi-benchmark" / evidence["run_id"]
    run_dir.mkdir(parents=True)
    evidence_path = run_dir / "evidence_manifest.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--evidence", str(evidence_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_evidence_rejects_aggregate_mismatch_and_artifact_traversal() -> None:
    validator = _load_validator()
    suite = _load_json(FIXTURE_SUITE_PATH)
    evidence = _real_evidence_from_example()
    evidence["aggregate_metrics"]["fixture_count"] = 29
    evidence["artifacts"]["summary_table"] = "../summary.csv"

    errors = validator.validate_evidence_manifest(evidence, suite, real_evidence=True)

    _assert_invalid(errors, "aggregate fixture_count must equal 30")
    _assert_invalid(errors, "artifact path must not traverse")


def test_real_evidence_rejects_placeholder_not_run_rows() -> None:
    validator = _load_validator()
    suite = _load_json(FIXTURE_SUITE_PATH)
    evidence = _real_evidence_from_example()
    evidence["per_fixture_results"][0]["gurobi_status"] = "not_run"
    evidence["per_fixture_results"][0]["gurobi_runtime_seconds"] = None
    evidence["aggregate_metrics"]["comparable_count"] = 29
    evidence["aggregate_metrics"]["objective_tolerance_pass_count"] = 29
    evidence["aggregate_metrics"]["status_parity_count"] = 29

    errors = validator.validate_evidence_manifest(evidence, suite, real_evidence=True)

    _assert_invalid(errors, "real evidence must not use placeholder status")
    _assert_invalid(errors, "real evidence requires runtime")


def test_fixture_id_drift_is_rejected() -> None:
    validator = _load_validator()
    suite = _load_json(FIXTURE_SUITE_PATH)
    suite["fixtures"][0]["id"] = "lp-999"

    errors = validator.validate_fixture_suite(suite)

    _assert_invalid(errors, "fixture ids must be lp-001 through lp-030")


def test_committed_expected_highs_baseline_matches_solver() -> None:
    sys.path.insert(0, str(SOLVER_SRC))
    from solver_orchestrator.solvers import solve_lp

    suite = _load_json(FIXTURE_SUITE_PATH)

    for fixture in suite["fixtures"]:
        result = solve_lp(
            c=fixture["objective"],
            a_constraints=fixture["constraints"]["A"],
            b_rhs=fixture["constraints"]["b"],
            x_lower=fixture["bounds"]["lower"],
            x_upper=fixture["bounds"]["upper"],
            sense=fixture["sense"],
        )
        expected = fixture["expected_highs"]
        assert result.status == expected["status"], fixture["id"]
        if result.objective is not None and expected.get("objective") is not None:
            assert (
                abs(result.objective - expected["objective"]) <= expected["objective_tolerance"]
            ), fixture["id"]


def test_expected_highs_baseline_rejects_objective_drift() -> None:
    sys.path.insert(0, str(SOLVER_SRC))
    from solver_orchestrator.solvers import solve_lp

    suite = _load_json(FIXTURE_SUITE_PATH)
    suite["fixtures"][0]["expected_highs"]["objective"] = 999.0
    fixture = suite["fixtures"][0]
    result = solve_lp(
        c=fixture["objective"],
        a_constraints=fixture["constraints"]["A"],
        b_rhs=fixture["constraints"]["b"],
        x_lower=fixture["bounds"]["lower"],
        x_upper=fixture["bounds"]["upper"],
        sense=fixture["sense"],
    )

    objective_delta = abs(result.objective - fixture["expected_highs"]["objective"])

    assert objective_delta > fixture["expected_highs"]["objective_tolerance"]
