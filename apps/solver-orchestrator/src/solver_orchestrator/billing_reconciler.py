"""Billing finalize retry reconciler — Story M2.2c.

Auto-remediation counterpart to 5.A.7's drift detection. Scans solver's
optimizations table for rows with `error.billing_finalize_failed=true`
(persisted by routes.post_optimization per AC1) and retries the finalize
call against billing-service.

Outcome per row:
- Success → clear flag, set billing_finalize_succeeded_at
- Failure (retry_count < max) → increment retry_count, update last_error
- Failure (retry_count == max) → tag billing_given_up_at for ops review

Pure-async; caller provides session. Use this module from billing_reconciler_cli
or M3's scheduler (K8s CronJob / Dramatiq) — see BILLING_RECONCILER.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator import billing_client


@dataclass(frozen=True)
class RetryOutcome:
    optimization_id: uuid.UUID
    user_id: uuid.UUID
    billing_charge_id: uuid.UUID
    attempt_number: int  # 1-based
    succeeded: bool
    error_message: str | None


@dataclass(frozen=True)
class RetryReport:
    pending_count: int
    succeeded_count: int
    failed_count: int  # transient: will retry next cycle
    exhausted_count: int  # gave up after max_retries
    results: list[RetryOutcome] = field(default_factory=list)


async def retry_pending_finalizes(
    session: AsyncSession,
    *,
    max_retries: int = 5,
    batch_limit: int = 100,
) -> RetryReport:
    """Scan + retry. Returns a structured report.

    Algorithm:
    1. SELECT optimizations rows where billing_finalize_failed=true AND retry_count < max
    2. For each row: call billing_client.finalize(...) with persisted retry context
    3. UPDATE row based on outcome
    """
    rows = await _fetch_pending(session, max_retries=max_retries, batch_limit=batch_limit)

    results: list[RetryOutcome] = []
    succeeded = 0
    failed = 0
    exhausted = 0

    for row in rows:
        opt_id, user_id, error_blob = row
        try:
            charge_id = uuid.UUID(error_blob["billing_charge_id"])
        except (KeyError, ValueError, TypeError):
            # Malformed retry context — mark as exhausted (skip silently next cycle)
            await _mark_given_up(session, opt_id, error="malformed retry context")
            exhausted += 1
            continue

        retry_count = int(error_blob.get("billing_retry_count", 0))
        attempt_number = retry_count + 1

        outcome = await billing_client.finalize(
            charge_id,
            user_id,
            elapsed_seconds=float(error_blob.get("billing_elapsed_seconds", 0.0)),
            status=error_blob.get("billing_status", "failure"),
            failure_reason=error_blob.get("billing_failure_reason"),
        )

        if outcome.ok:
            current_state = (
                outcome.body.get("current_state") if isinstance(outcome.body, dict) else None
            )
            await _mark_succeeded(
                session,
                opt_id,
                current_state=current_state,
                status_code=outcome.status_code,
                is_cancel_finalize=error_blob.get("billing_cancel_finalize_failed") is True,
            )
            succeeded += 1
            results.append(
                RetryOutcome(
                    optimization_id=opt_id,
                    user_id=user_id,
                    billing_charge_id=charge_id,
                    attempt_number=attempt_number,
                    succeeded=True,
                    error_message=None,
                )
            )
        else:
            new_count = attempt_number
            if new_count >= max_retries:
                await _mark_given_up(session, opt_id, error=outcome.error_message)
                exhausted += 1
            else:
                await _mark_failed_increment(session, opt_id, new_count, outcome.error_message)
                failed += 1
            results.append(
                RetryOutcome(
                    optimization_id=opt_id,
                    user_id=user_id,
                    billing_charge_id=charge_id,
                    attempt_number=attempt_number,
                    succeeded=False,
                    error_message=outcome.error_message,
                )
            )

    await session.commit()

    return RetryReport(
        pending_count=len(rows),
        succeeded_count=succeeded,
        failed_count=failed,
        exhausted_count=exhausted,
        results=results,
    )


async def _fetch_pending(
    session: AsyncSession, *, max_retries: int, batch_limit: int
) -> list[tuple[uuid.UUID, uuid.UUID, dict[str, Any]]]:
    """SELECT pending rows. JSONB filter handles missing keys via COALESCE/cast."""
    stmt = text(
        """
        SELECT id, user_id, error
        FROM optimizations
        WHERE error ->> 'billing_finalize_failed' = 'true'
          AND COALESCE((error ->> 'billing_retry_count')::int, 0) < :max_retries
          AND error ->> 'billing_finalize_succeeded_at' IS NULL
        ORDER BY created_at ASC
        LIMIT :batch_limit
        """
    )
    rows = (
        await session.execute(stmt, {"max_retries": max_retries, "batch_limit": batch_limit})
    ).all()
    return [
        (cast(uuid.UUID, r[0]), cast(uuid.UUID, r[1]), cast("dict[str, Any]", r[2])) for r in rows
    ]


async def _mark_succeeded(
    session: AsyncSession,
    opt_id: uuid.UUID,
    *,
    current_state: str | None,
    status_code: int,
    is_cancel_finalize: bool,
) -> None:
    """Clear the failed flag + record success timestamp."""
    now_iso = datetime.now(UTC).isoformat()
    if is_cancel_finalize:
        await _mark_cancel_succeeded(
            session,
            opt_id,
            now_iso=now_iso,
            current_state=current_state,
            status_code=status_code,
        )
        return
    stmt = text(
        """
        UPDATE optimizations
        SET error = (
            error
            - 'billing_finalize_failed'
            - 'billing_finalize_error'
            - 'billing_retry_count'
        ) || jsonb_build_object('billing_finalize_succeeded_at', CAST(:now AS text))
        WHERE id = :id
        """
    )
    await session.execute(stmt, {"id": opt_id, "now": now_iso})


async def _mark_cancel_succeeded(
    session: AsyncSession,
    opt_id: uuid.UUID,
    *,
    now_iso: str,
    current_state: str | None,
    status_code: int,
) -> None:
    """Clear cancel retry flags and advance persisted refund status."""
    refund_status = "refunded" if current_state == "refunded" else "finalized"
    stmt = text(
        """
        UPDATE optimizations
        SET
            error = (
                error
                - 'billing_finalize_failed'
                - 'billing_cancel_finalize_failed'
                - 'billing_finalize_error'
                - 'billing_finalize_last_error'
                - 'billing_retry_count'
            ) || jsonb_build_object(
                'billing_finalize_succeeded_at', CAST(:now AS text),
                'refund_status', CAST(:refund_status AS text)
            ),
            input_payload = CASE
                WHEN input_payload #> '{_system,billing}' IS NULL THEN input_payload
                ELSE jsonb_set(
                    input_payload,
                    '{_system,billing}',
                    (input_payload #> '{_system,billing}') || jsonb_build_object(
                        'refund_status', CAST(:refund_status AS text),
                        'cancel_finalize_status', CAST(:status_code AS int)
                    ),
                    true
                )
            END
        WHERE id = :id
        """
    )
    await session.execute(
        stmt,
        {
            "id": opt_id,
            "now": now_iso,
            "refund_status": refund_status,
            "status_code": status_code,
        },
    )


async def _mark_failed_increment(
    session: AsyncSession,
    opt_id: uuid.UUID,
    new_count: int,
    error_message: str | None,
) -> None:
    """Bump retry_count + update last_error."""
    stmt = text(
        """
        UPDATE optimizations
        SET error = error || jsonb_build_object(
            'billing_retry_count', CAST(:count AS int),
            'billing_finalize_last_error', CAST(:err AS text)
        )
        WHERE id = :id
        """
    )
    await session.execute(
        stmt, {"id": opt_id, "count": new_count, "err": error_message or "unknown"}
    )


async def _mark_given_up(session: AsyncSession, opt_id: uuid.UUID, *, error: str | None) -> None:
    """Tag billing_given_up_at; ops must review."""
    now_iso = datetime.now(UTC).isoformat()
    stmt = text(
        """
        UPDATE optimizations
        SET error = error || jsonb_build_object(
            'billing_given_up_at', CAST(:now AS text),
            'billing_finalize_last_error', CAST(:err AS text)
        )
        WHERE id = :id
        """
    )
    await session.execute(stmt, {"id": opt_id, "now": now_iso, "err": error or "exhausted retries"})


__all__ = ["RetryOutcome", "RetryReport", "retry_pending_finalizes"]
