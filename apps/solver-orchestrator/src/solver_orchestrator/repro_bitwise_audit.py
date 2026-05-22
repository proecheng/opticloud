"""Voucher bitwise reproducibility audit utilities.

Story 6.B.7 keeps this module side-effect-light: callers provide a database
session, the audit reads voucher/source rows, reruns supported LP payloads
in-process, and returns a report without creating child vouchers.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator import solvers
from solver_orchestrator.models import Optimization, ReproductionVoucher
from solver_orchestrator.schemas import OptimizationRequest

DEFAULT_SAMPLE_RATE = 0.05
DEFAULT_PASS_THRESHOLD = 0.95
DEFAULT_EXECUTABLE_COVERAGE_THRESHOLD = 0.95
DEFAULT_SEED = "quarterly"

SampleStatus = Literal["passed", "failed", "skipped"]
ReportStatus = Literal[
    "passed",
    "failed",
    "no_eligible_vouchers",
    "insufficient_executable_coverage",
]


@dataclass(frozen=True)
class AuditPolicy:
    sample_rate: float = DEFAULT_SAMPLE_RATE
    seed: str = DEFAULT_SEED
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))
    pass_threshold: float = DEFAULT_PASS_THRESHOLD
    executable_coverage_threshold: float = DEFAULT_EXECUTABLE_COVERAGE_THRESHOLD

    def __post_init__(self) -> None:
        _validate_unit_interval(self.sample_rate, "sample_rate")
        _validate_unit_interval(self.pass_threshold, "pass_threshold")
        _validate_unit_interval(
            self.executable_coverage_threshold,
            "executable_coverage_threshold",
        )


@dataclass(frozen=True)
class VoucherAuditCandidate:
    voucher_id: str
    optimization_id: uuid.UUID
    task_type: str
    locked_solver: str
    locked_model_version: dict[str, Any]
    rerun_depth: int
    created_at: datetime
    input_payload: dict[str, Any]
    solution: dict[str, Any] | None
    objective: float | Decimal | None


@dataclass(frozen=True)
class AuditSampleResult:
    voucher_id: str
    optimization_id: uuid.UUID
    task_type: str
    locked_solver: str
    rerun_depth: int
    status: SampleStatus
    reason: str
    expected_digest: str | None = None
    observed_digest: str | None = None


@dataclass(frozen=True)
class IneligibleCounts:
    revoked: int = 0
    expired: int = 0
    missing_source: int = 0
    non_completed_source: int = 0


@dataclass(frozen=True)
class AuditReport:
    generated_at: datetime
    policy: AuditPolicy
    eligible_count: int
    sampled_count: int
    passed_count: int
    failed_count: int
    skipped_count: int
    pass_rate: float | None
    executable_coverage: float | None
    status: ReportStatus
    ineligible_counts: IneligibleCounts
    results: list[AuditSampleResult]


def _validate_unit_interval(value: float, field_name: str) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be between 0 and 1")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _add_calendar_years_utc(value: datetime, years: int) -> datetime:
    value_utc = _as_utc(value)
    try:
        return value_utc.replace(year=value_utc.year + years)
    except ValueError:
        if value_utc.month == 2 and value_utc.day == 29:
            return value_utc.replace(year=value_utc.year + years, month=2, day=28)
        raise


def is_voucher_expired(created_at: datetime, *, as_of: datetime) -> bool:
    return _as_utc(as_of) >= _add_calendar_years_utc(created_at, 5)


def strip_system_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    clean = dict(payload)
    clean.pop("_system", None)
    return clean


def canonical_json(value: Any) -> str:
    return json.dumps(
        _canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()}"


def canonical_result_payload(
    *,
    status: str,
    objective: float | Decimal | None,
    solution: Mapping[str, Any] | None,
    locked_model_version: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "objective": float(objective) if objective is not None else None,
        "solution": dict(solution) if solution is not None else None,
        "locked_model_version": dict(locked_model_version),
    }


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    return value


def sample_candidates(
    candidates: Sequence[VoucherAuditCandidate],
    *,
    policy: AuditPolicy,
) -> list[VoucherAuditCandidate]:
    if not candidates or policy.sample_rate <= 0:
        return []
    sample_size = max(1, math.ceil(len(candidates) * policy.sample_rate))
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            hashlib.sha256(
                (
                    f"{policy.seed}:{_as_utc(policy.as_of).isoformat()}:"
                    f"{candidate.voucher_id}"
                ).encode()
            ).hexdigest(),
            candidate.voucher_id,
            str(candidate.optimization_id),
        ),
    )
    return ranked[:sample_size]


async def load_audit_candidates(
    session: AsyncSession,
    *,
    as_of: datetime,
) -> tuple[list[VoucherAuditCandidate], IneligibleCounts]:
    rows = (
        await session.execute(
            select(ReproductionVoucher, Optimization)
            .outerjoin(Optimization, ReproductionVoucher.optimization_id == Optimization.id)
            .order_by(ReproductionVoucher.voucher_id.asc())
        )
    ).all()

    candidates: list[VoucherAuditCandidate] = []
    revoked = expired = missing_source = non_completed_source = 0
    for voucher, optimization in rows:
        voucher = cast(ReproductionVoucher, voucher)
        optimization = cast(Optimization | None, optimization)
        if voucher.status != "issued":
            revoked += 1
            continue
        if optimization is None:
            missing_source += 1
            continue
        if optimization.status != "completed":
            non_completed_source += 1
            continue
        if is_voucher_expired(voucher.created_at, as_of=as_of):
            expired += 1
            continue
        candidates.append(
            VoucherAuditCandidate(
                voucher_id=voucher.voucher_id,
                optimization_id=voucher.optimization_id,
                task_type=optimization.task_type,
                locked_solver=voucher.locked_solver,
                locked_model_version=dict(voucher.locked_model_version),
                rerun_depth=voucher.rerun_depth,
                created_at=voucher.created_at,
                input_payload=dict(optimization.input_payload),
                solution=optimization.solution,
                objective=optimization.objective,
            )
        )

    return (
        candidates,
        IneligibleCounts(
            revoked=revoked,
            expired=expired,
            missing_source=missing_source,
            non_completed_source=non_completed_source,
        ),
    )


def audit_candidate(candidate: VoucherAuditCandidate) -> AuditSampleResult:
    if candidate.task_type != "lp":
        return _skipped(candidate, f"unsupported_task_type:{candidate.task_type}")
    if candidate.locked_solver != "highs":
        return _skipped(candidate, f"unsupported_locked_solver:{candidate.locked_solver}")

    clean_payload = strip_system_metadata(candidate.input_payload)
    try:
        request = OptimizationRequest.model_validate(clean_payload)
    except Exception as exc:
        return _skipped(candidate, f"invalid_source_payload:{type(exc).__name__}")

    request_payload = request.model_dump(by_alias=True)
    expected_payload = canonical_result_payload(
        status="completed",
        objective=candidate.objective,
        solution=candidate.solution,
        locked_model_version=candidate.locked_model_version,
    )
    expected_digest = sha256_digest(expected_payload)

    result = solvers.solve_from_request(
        request_payload,
        max_solve_seconds=request.options.max_solve_seconds,
    )
    observed_payload = canonical_result_payload(
        status="completed" if result.status == "optimal" else result.status,
        objective=result.objective,
        solution=result.solution,
        locked_model_version=candidate.locked_model_version,
    )
    observed_digest = sha256_digest(observed_payload)
    if expected_digest == observed_digest:
        return AuditSampleResult(
            voucher_id=candidate.voucher_id,
            optimization_id=candidate.optimization_id,
            task_type=candidate.task_type,
            locked_solver=candidate.locked_solver,
            rerun_depth=candidate.rerun_depth,
            status="passed",
            reason="bitwise_digest_match",
            expected_digest=expected_digest,
            observed_digest=observed_digest,
        )
    return AuditSampleResult(
        voucher_id=candidate.voucher_id,
        optimization_id=candidate.optimization_id,
        task_type=candidate.task_type,
        locked_solver=candidate.locked_solver,
        rerun_depth=candidate.rerun_depth,
        status="failed",
        reason=f"bitwise_digest_mismatch:{result.status}",
        expected_digest=expected_digest,
        observed_digest=observed_digest,
    )


def _skipped(candidate: VoucherAuditCandidate, reason: str) -> AuditSampleResult:
    return AuditSampleResult(
        voucher_id=candidate.voucher_id,
        optimization_id=candidate.optimization_id,
        task_type=candidate.task_type,
        locked_solver=candidate.locked_solver,
        rerun_depth=candidate.rerun_depth,
        status="skipped",
        reason=reason,
    )


async def run_repro_bitwise_audit(
    session: AsyncSession,
    *,
    policy: AuditPolicy | None = None,
    generated_at: datetime | None = None,
) -> AuditReport:
    policy = policy or AuditPolicy()
    generated_at = generated_at or datetime.now(UTC)
    candidates, ineligible_counts = await load_audit_candidates(session, as_of=policy.as_of)
    sampled = sample_candidates(candidates, policy=policy)
    results = [audit_candidate(candidate) for candidate in sampled]
    return build_audit_report(
        policy=policy,
        generated_at=generated_at,
        eligible_count=len(candidates),
        results=results,
        ineligible_counts=ineligible_counts,
    )


def build_audit_report(
    *,
    policy: AuditPolicy,
    generated_at: datetime,
    eligible_count: int,
    results: Sequence[AuditSampleResult],
    ineligible_counts: IneligibleCounts | None = None,
) -> AuditReport:
    passed = sum(1 for result in results if result.status == "passed")
    failed = sum(1 for result in results if result.status == "failed")
    skipped = sum(1 for result in results if result.status == "skipped")
    sampled = len(results)
    executable = passed + failed
    pass_rate = passed / executable if executable else None
    executable_coverage = executable / sampled if sampled else None

    if eligible_count == 0:
        status: ReportStatus = "no_eligible_vouchers"
    elif sampled == 0 or executable == 0:
        status = "insufficient_executable_coverage"
    elif (
        executable_coverage is not None
        and executable_coverage < policy.executable_coverage_threshold
    ):
        status = "insufficient_executable_coverage"
    elif pass_rate is not None and pass_rate < policy.pass_threshold:
        status = "failed"
    else:
        status = "passed"

    return AuditReport(
        generated_at=generated_at,
        policy=policy,
        eligible_count=eligible_count,
        sampled_count=sampled,
        passed_count=passed,
        failed_count=failed,
        skipped_count=skipped,
        pass_rate=pass_rate,
        executable_coverage=executable_coverage,
        status=status,
        ineligible_counts=ineligible_counts or IneligibleCounts(),
        results=list(results),
    )


def report_to_dict(report: AuditReport) -> dict[str, Any]:
    return {
        "generated_at": _as_utc(report.generated_at).isoformat(),
        "as_of": _as_utc(report.policy.as_of).isoformat(),
        "sample_policy": {
            "sample_rate": report.policy.sample_rate,
            "seed": report.policy.seed,
            "pass_threshold": report.policy.pass_threshold,
            "executable_coverage_threshold": report.policy.executable_coverage_threshold,
        },
        "eligible_count": report.eligible_count,
        "sampled_count": report.sampled_count,
        "passed_count": report.passed_count,
        "failed_count": report.failed_count,
        "skipped_count": report.skipped_count,
        "pass_rate": report.pass_rate,
        "executable_coverage": report.executable_coverage,
        "status": report.status,
        "ineligible_counts": {
            "revoked": report.ineligible_counts.revoked,
            "expired": report.ineligible_counts.expired,
            "missing_source": report.ineligible_counts.missing_source,
            "non_completed_source": report.ineligible_counts.non_completed_source,
        },
        "results": [sample_result_to_dict(result) for result in report.results],
    }


def sample_result_to_dict(result: AuditSampleResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "voucher_id": result.voucher_id,
        "optimization_id": str(result.optimization_id),
        "task_type": result.task_type,
        "locked_solver": result.locked_solver,
        "rerun_depth": result.rerun_depth,
        "status": result.status,
        "reason": result.reason,
    }
    if result.expected_digest is not None:
        payload["expected_digest"] = result.expected_digest
    if result.observed_digest is not None:
        payload["observed_digest"] = result.observed_digest
    return payload


def render_markdown_report(report: AuditReport) -> str:
    lines = [
        "# Repro Bitwise Audit Report",
        "",
        f"Generated: {_as_utc(report.generated_at).isoformat()}",
        f"As of: {_as_utc(report.policy.as_of).isoformat()}",
        f"Status: {report.status}",
        f"Sample rate: {report.policy.sample_rate}",
        f"Seed: `{report.policy.seed}`",
        f"Eligible vouchers: {report.eligible_count}",
        f"Sampled vouchers: {report.sampled_count}",
        f"Passed: {report.passed_count}",
        f"Failed: {report.failed_count}",
        f"Skipped: {report.skipped_count}",
        f"Pass rate: {_rate_label(report.pass_rate)}",
        f"Executable coverage: {_rate_label(report.executable_coverage)}",
        "",
        "## Ineligible Counts",
        "",
        f"- Revoked: {report.ineligible_counts.revoked}",
        f"- Expired: {report.ineligible_counts.expired}",
        f"- Missing source: {report.ineligible_counts.missing_source}",
        f"- Non-completed source: {report.ineligible_counts.non_completed_source}",
        "",
        "## Failed / Skipped Samples",
        "",
        "| voucher_id | optimization_id | status | reason | expected_digest | observed_digest |",
        "|---|---|---|---|---|---|",
    ]
    noteworthy = [result for result in report.results if result.status != "passed"]
    if noteworthy:
        for result in noteworthy:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(result.voucher_id),
                        str(result.optimization_id),
                        result.status,
                        _md_cell(result.reason),
                        result.expected_digest or "",
                        result.observed_digest or "",
                    ]
                )
                + " |"
            )
    else:
        lines.append("| _none_ |  |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)


def _rate_label(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def write_report(path: Path, report: AuditReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report_to_dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_markdown_report(path: Path, report: AuditReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_report(report), encoding="utf-8")


__all__ = [
    "AuditPolicy",
    "AuditReport",
    "AuditSampleResult",
    "IneligibleCounts",
    "VoucherAuditCandidate",
    "audit_candidate",
    "build_audit_report",
    "canonical_json",
    "canonical_result_payload",
    "load_audit_candidates",
    "render_markdown_report",
    "report_to_dict",
    "run_repro_bitwise_audit",
    "sample_candidates",
    "sha256_digest",
    "strip_system_metadata",
    "write_markdown_report",
    "write_report",
]
