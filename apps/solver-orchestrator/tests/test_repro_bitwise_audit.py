"""Story 6.B.7 — voucher bitwise reproducibility audit tests."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from solver_orchestrator.config import settings
from solver_orchestrator.models import IdempotencyKey, Optimization, ReproductionVoucher
from solver_orchestrator.repro import generate_reproduction_voucher_id
from solver_orchestrator.repro_bitwise_audit import (
    AuditPolicy,
    AuditSampleResult,
    VoucherAuditCandidate,
    audit_candidate,
    build_audit_report,
    canonical_result_payload,
    render_markdown_report,
    report_to_dict,
    run_repro_bitwise_audit,
    sample_candidates,
    sha256_digest,
)
from solver_orchestrator.repro_bitwise_audit_cli import main
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)
NOW = datetime(2026, 5, 22, tzinfo=UTC)
MODEL_VERSION = {
    "provider_id": "highs",
    "kind": "open_source",
    "version": "1.7.0",
    "provider_url": "https://highs.dev/",
}
LP_PAYLOAD = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
    "options": {"max_solve_seconds": 30.0, "reproducible": True},
    "_system": {"reproducibility": {"voucher_id": "repro-2026-ABC123"}},
}
LP_SOLUTION = {"x": [0.0, 0.0]}


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


def _candidate(
    voucher_id: str,
    *,
    task_type: str = "lp",
    locked_solver: str = "highs",
    solution: dict[str, object] | None = None,
    objective: float = 0.0,
) -> VoucherAuditCandidate:
    return VoucherAuditCandidate(
        voucher_id=voucher_id,
        optimization_id=uuid.uuid4(),
        task_type=task_type,
        locked_solver=locked_solver,
        locked_model_version=dict(MODEL_VERSION),
        rerun_depth=0,
        created_at=NOW,
        input_payload=dict(LP_PAYLOAD),
        solution=solution if solution is not None else dict(LP_SOLUTION),
        objective=objective,
    )


def test_sample_candidates_is_deterministic_and_uses_minimum_one() -> None:
    candidates = [_candidate(f"repro-2026-AAAAA{i}") for i in range(10)]
    policy = AuditPolicy(sample_rate=0.05, seed="q1", as_of=NOW)

    first = sample_candidates(candidates, policy=policy)
    second = sample_candidates(list(reversed(candidates)), policy=policy)

    assert len(first) == 1
    assert [item.voucher_id for item in first] == [item.voucher_id for item in second]


def test_sample_policy_rejects_invalid_rate() -> None:
    with pytest.raises(ValueError, match="sample_rate"):
        AuditPolicy(sample_rate=1.01, as_of=NOW)


def test_canonical_digest_excludes_nondeterministic_metadata() -> None:
    base = canonical_result_payload(
        status="completed",
        objective=0.0,
        solution=LP_SOLUTION,
        locked_model_version=MODEL_VERSION,
    )
    with_noise = {
        **base,
        "solve_seconds": 0.123,
        "created_at": NOW.isoformat(),
        "optimization_id": str(uuid.uuid4()),
    }

    assert sha256_digest(base) != sha256_digest(with_noise)
    assert sha256_digest(base) == sha256_digest(
        canonical_result_payload(
            status="completed",
            objective=0.0,
            solution=LP_SOLUTION,
            locked_model_version=MODEL_VERSION,
        )
    )


def test_audit_candidate_passes_strict_digest_for_matching_lp() -> None:
    result = audit_candidate(_candidate("repro-2026-PASS01"))

    assert result.status == "passed"
    assert result.reason == "bitwise_digest_match"
    assert result.expected_digest == result.observed_digest


def test_audit_candidate_fails_on_digest_mismatch() -> None:
    result = audit_candidate(
        _candidate("repro-2026-FAIL01", solution={"x": [1.0, 1.0]}, objective=2.0)
    )

    assert result.status == "failed"
    assert result.expected_digest != result.observed_digest
    assert "bitwise_digest_mismatch" in result.reason


def test_audit_candidate_skips_unsupported_task_and_solver() -> None:
    task = audit_candidate(_candidate("repro-2026-SKIP01", task_type="forecast"))
    solver = audit_candidate(_candidate("repro-2026-SKIP02", locked_solver="custom"))

    assert task.status == "skipped"
    assert task.reason == "unsupported_task_type:forecast"
    assert solver.status == "skipped"
    assert solver.reason == "unsupported_locked_solver:custom"


def test_report_status_and_markdown_do_not_dump_payloads() -> None:
    report = build_audit_report(
        policy=AuditPolicy(sample_rate=1.0, as_of=NOW),
        generated_at=NOW,
        eligible_count=2,
        results=[
            AuditSampleResult(
                voucher_id="repro-2026-PASS01",
                optimization_id=uuid.uuid4(),
                task_type="lp",
                locked_solver="highs",
                rerun_depth=0,
                status="passed",
                reason="bitwise_digest_match",
                expected_digest="sha256:a",
                observed_digest="sha256:a",
            ),
            AuditSampleResult(
                voucher_id="repro-2026-SKIP01",
                optimization_id=uuid.uuid4(),
                task_type="forecast",
                locked_solver="chronos",
                rerun_depth=0,
                status="skipped",
                reason="unsupported_task_type:forecast",
            ),
        ],
    )

    markdown = render_markdown_report(report)
    report_json = json.dumps(report_to_dict(report), ensure_ascii=False)
    assert report.status == "insufficient_executable_coverage"
    assert "unsupported_task_type:forecast" in markdown
    for serialized in (markdown, report_json):
        assert "minimize" not in serialized
        assert "api_key" not in serialized.lower()
        assert "user_id" not in serialized.lower()


async def _count_rows(engine: AsyncEngine) -> dict[str, int]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        return {
            "optimizations": (
                await session.execute(select(func.count()).select_from(Optimization))
            ).scalar_one(),
            "vouchers": (
                await session.execute(select(func.count()).select_from(ReproductionVoucher))
            ).scalar_one(),
            "idempotency": (
                await session.execute(select(func.count()).select_from(IdempotencyKey))
            ).scalar_one(),
        }


async def _seed_voucher(
    session: AsyncSession,
    *,
    voucher_id: str,
    task_type: str = "lp",
    locked_solver: str = "highs",
    voucher_status: str = "issued",
    optimization_status: str = "completed",
    created_at: datetime = NOW,
) -> None:
    opt = Optimization(
        user_id=uuid.uuid4(),
        api_key_id=uuid.uuid4(),
        task_type=task_type,
        status=optimization_status,
        input_payload={
            **LP_PAYLOAD,
            "task_type": task_type,
        },
        solution=dict(LP_SOLUTION),
        objective=0.0,
        model_version=dict(MODEL_VERSION),
        solve_seconds=0.01,
        created_at=created_at,
        completed_at=created_at if optimization_status == "completed" else None,
    )
    opt.id = uuid.uuid4()
    session.add(opt)
    await session.flush()
    session.add(
        ReproductionVoucher(
            voucher_id=voucher_id,
            optimization_id=opt.id,
            user_id=opt.user_id,
            api_key_id=opt.api_key_id,
            request_fingerprint=f"sha256:{uuid.uuid4().hex}",
            locked_model_version=dict(MODEL_VERSION),
            locked_solver=locked_solver,
            seed_locked=True,
            seed=None,
            status=voucher_status,
            created_at=created_at,
        )
    )


async def test_run_audit_filters_ineligible_and_preserves_row_counts(db_engine) -> None:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await _seed_voucher(session, voucher_id=generate_reproduction_voucher_id(NOW))
        await _seed_voucher(
            session,
            voucher_id=generate_reproduction_voucher_id(NOW),
            voucher_status="revoked",
        )
        await _seed_voucher(
            session,
            voucher_id=generate_reproduction_voucher_id(datetime(2020, 1, 1, tzinfo=UTC)),
            created_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        await _seed_voucher(
            session,
            voucher_id=generate_reproduction_voucher_id(NOW),
            locked_solver="custom",
        )
        await _seed_voucher(
            session,
            voucher_id=generate_reproduction_voucher_id(NOW),
            optimization_status="failed",
        )
        await session.commit()

    before = await _count_rows(db_engine)
    async with maker() as session:
        report = await run_repro_bitwise_audit(
            session,
            policy=AuditPolicy(sample_rate=1.0, seed="integration", as_of=NOW),
            generated_at=NOW,
        )
    after = await _count_rows(db_engine)

    assert after == before
    assert report.eligible_count >= 2
    assert report.passed_count >= 1
    assert report.skipped_count >= 1
    assert report.ineligible_counts.revoked >= 1
    assert report.ineligible_counts.expired >= 1
    assert report.ineligible_counts.non_completed_source >= 1


def test_cli_writes_json_markdown_and_stdout(tmp_path, capsys, monkeypatch) -> None:
    import solver_orchestrator.repro_bitwise_audit_cli as cli

    report = build_audit_report(
        policy=AuditPolicy(sample_rate=1.0, as_of=NOW),
        generated_at=NOW,
        eligible_count=1,
        results=[
            AuditSampleResult(
                voucher_id="repro-2026-PASS01",
                optimization_id=uuid.uuid4(),
                task_type="lp",
                locked_solver="highs",
                rerun_depth=0,
                status="passed",
                reason="bitwise_digest_match",
                expected_digest="sha256:a",
                observed_digest="sha256:a",
            )
        ],
    )

    async def fake_run_repro_bitwise_audit(*_args, **_kwargs):
        return report

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    class FakeEngine:
        async def dispose(self) -> None:
            return None

    def fake_sessionmaker(*_args, **_kwargs):
        return lambda: FakeSession()

    monkeypatch.setattr(cli, "create_async_engine", lambda *_args, **_kwargs: FakeEngine())
    monkeypatch.setattr(cli, "async_sessionmaker", fake_sessionmaker)
    monkeypatch.setattr(cli, "run_repro_bitwise_audit", fake_run_repro_bitwise_audit)

    report_path = tmp_path / "latest.json"
    markdown_path = tmp_path / "latest.md"
    exit_code = main(
        [
            "--out",
            str(report_path),
            "--markdown",
            str(markdown_path),
            "--as-of",
            NOW.isoformat(),
        ]
    )

    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["event"] == "repro.bitwise.audit.report"
    assert stdout_payload["status"] == "passed"
    assert report_payload["status"] == "passed"
    assert report_payload["results"][0]["voucher_id"] == "repro-2026-PASS01"
    assert "# Repro Bitwise Audit Report" in markdown_path.read_text(encoding="utf-8")


def test_cli_rejects_invalid_sample_rate(capsys) -> None:
    exit_code = main(["--sample-rate", "1.2"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "sample_rate" in captured.err
