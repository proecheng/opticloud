"""Reproduction voucher issuance helpers (Story 6.B.2 + 6.B.3)."""

from __future__ import annotations

import re
import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator.models import Optimization, ReproductionVoucher

CROCKFORD_BASE32_ALPHABET = "0123456789" + "ABCDEFGHJK" + "MNPQRSTVWXYZ"
VOUCHER_ID_PATTERN = re.compile(r"^repro-[0-9]{4}-[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{6}$")
MAX_VOUCHER_ID_ATTEMPTS = 8


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def generate_reproduction_voucher_id(issued_at: datetime) -> str:
    """Return `repro-{YYYY}-{6 chars}` using the PRD voucher alphabet."""
    issued_at_utc = _as_utc(issued_at)
    suffix = "".join(secrets.choice(CROCKFORD_BASE32_ALPHABET) for _ in range(6))
    return f"repro-{issued_at_utc.year}-{suffix}"


def _extract_reproducibility_handoff(opt: Optimization) -> dict[str, Any]:
    system_payload = opt.input_payload.get("_system")
    if not isinstance(system_payload, dict):
        raise ValueError("optimization has no reproducibility system payload")
    reproducibility = system_payload.get("reproducibility")
    if not isinstance(reproducibility, dict):
        raise ValueError("optimization has no reproducibility handoff")
    return cast(dict[str, Any], reproducibility)


def _clone_model_json(value: dict[str, Any]) -> dict[str, Any]:
    return dict(value)


def _seed_from_handoff(handoff: dict[str, Any]) -> int | None:
    seed = handoff.get("seed")
    if seed is None:
        return None
    if type(seed) is int:
        return seed
    raise ValueError("reproducibility seed must be int or null")


def _bool_from_handoff(handoff: dict[str, Any], key: str) -> bool:
    value = handoff.get(key)
    if type(value) is bool:
        return value
    raise ValueError(f"reproducibility {key} must be boolean")


def _str_from_handoff(handoff: dict[str, Any], key: str) -> str:
    value = handoff.get(key)
    if isinstance(value, str) and value:
        return value
    raise ValueError(f"reproducibility {key} must be a non-empty string")


def _dict_from_handoff(handoff: dict[str, Any], key: str) -> dict[str, Any]:
    value = handoff.get(key)
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    raise ValueError(f"reproducibility {key} must be an object")


def attach_voucher_id_to_optimization(opt: Optimization, voucher_id: str) -> None:
    """Persist voucher_id into `Optimization.input_payload._system.reproducibility`.

    SQLAlchemy does not reliably detect nested JSONB mutations; assign a fresh
    dict so the change is flushed.
    """
    payload = dict(opt.input_payload)
    system_payload = payload.get("_system")
    system = dict(system_payload) if isinstance(system_payload, dict) else {}
    reproducibility_payload = system.get("reproducibility")
    if not isinstance(reproducibility_payload, dict):
        return
    reproducibility = dict(reproducibility_payload)
    if reproducibility.get("voucher_id") == voucher_id:
        return
    reproducibility["voucher_id"] = voucher_id
    system["reproducibility"] = reproducibility
    payload["_system"] = system
    opt.input_payload = payload


async def get_reproduction_voucher(
    session: AsyncSession, optimization_id: uuid.UUID
) -> ReproductionVoucher | None:
    result = await session.execute(
        select(ReproductionVoucher).where(ReproductionVoucher.optimization_id == optimization_id)
    )
    return result.scalar_one_or_none()


async def get_reproduction_voucher_by_id(
    session: AsyncSession, voucher_id: str
) -> ReproductionVoucher | None:
    result = await session.execute(
        select(ReproductionVoucher).where(ReproductionVoucher.voucher_id == voucher_id)
    )
    return result.scalar_one_or_none()


async def get_reproduction_voucher_by_pk(
    session: AsyncSession, voucher_pk: uuid.UUID
) -> ReproductionVoucher | None:
    result = await session.execute(
        select(ReproductionVoucher).where(ReproductionVoucher.id == voucher_pk)
    )
    return result.scalar_one_or_none()


def build_rerun_lineage_payload(
    *,
    rerun_of_voucher_id: str,
    source_optimization_id: uuid.UUID,
    archive_restore: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rerun_of_voucher_id": rerun_of_voucher_id,
        "source_optimization_id": str(source_optimization_id),
    }
    if archive_restore is not None:
        payload["archive_restore"] = _clone_model_json(archive_restore)
    return payload


async def attach_existing_voucher_id(
    session: AsyncSession,
    opt: Optimization,
) -> str | None:
    voucher = await get_reproduction_voucher(session, opt.id)
    if voucher is None:
        return None
    attach_voucher_id_to_optimization(opt, voucher.voucher_id)
    return voucher.voucher_id


async def issue_reproduction_voucher(
    session: AsyncSession,
    opt: Optimization,
    *,
    issued_at: datetime | None = None,
    voucher_id_factory: Callable[[datetime], str] = generate_reproduction_voucher_id,
    max_attempts: int = MAX_VOUCHER_ID_ATTEMPTS,
    parent_voucher_id: uuid.UUID | None = None,
    rerun_depth: int = 0,
) -> str:
    """Issue one durable voucher for a completed reproducible optimization."""
    if opt.status != "completed":
        raise ValueError("reproduction voucher can only be issued for completed optimizations")

    existing = await get_reproduction_voucher(session, opt.id)
    if existing is not None:
        attach_voucher_id_to_optimization(opt, existing.voucher_id)
        return existing.voucher_id

    handoff = _extract_reproducibility_handoff(opt)
    created_at = _as_utc(issued_at or datetime.now(UTC))
    request_fingerprint = _str_from_handoff(handoff, "request_fingerprint")
    locked_model_version = _dict_from_handoff(handoff, "locked_model_version")
    locked_solver = _str_from_handoff(handoff, "locked_solver")
    seed_locked = _bool_from_handoff(handoff, "seed_locked")
    seed = _seed_from_handoff(handoff)

    for _ in range(max_attempts):
        voucher_id = voucher_id_factory(created_at)
        try:
            async with session.begin_nested():
                session.add(
                    ReproductionVoucher(
                        voucher_id=voucher_id,
                        optimization_id=opt.id,
                        parent_voucher_id=parent_voucher_id,
                        rerun_depth=rerun_depth,
                        user_id=opt.user_id,
                        api_key_id=opt.api_key_id,
                        request_fingerprint=request_fingerprint,
                        locked_model_version=locked_model_version,
                        locked_solver=locked_solver,
                        seed_locked=seed_locked,
                        seed=seed,
                        status="issued",
                        created_at=created_at,
                    )
                )
                await session.flush()
        except IntegrityError:
            existing_after_conflict = await get_reproduction_voucher(session, opt.id)
            if existing_after_conflict is not None:
                attach_voucher_id_to_optimization(opt, existing_after_conflict.voucher_id)
                return existing_after_conflict.voucher_id
            continue

        attach_voucher_id_to_optimization(opt, voucher_id)
        return voucher_id

    raise RuntimeError("failed to issue a unique reproduction voucher after bounded retries")
