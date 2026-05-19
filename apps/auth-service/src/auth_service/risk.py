"""Story 1.5 — FR A5 / NFR-S6 risk-detection evaluator.

Pure-ish module: takes a Session + user_id, evaluates ENABLED rules at
signup time, persists RiskFlag rows for triggers, and flips
`User.is_frozen` when distinct enabled rule triggers across user history
reach `FREEZE_THRESHOLD`.

v1 auto-detection fires only `ip_24_share` (the only signal source ready
today). Admin manual flags count toward the same threshold via the same
evaluator path. As future stories bring more signals online (FE
fingerprint, solver telemetry, billing payment), they flip
`risk_rules.enabled=true` for their rule and the system becomes more
automatic without further freeze-logic changes.
"""

from __future__ import annotations

import ipaddress
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import and_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import AuditLog, RiskFlag, RiskRule, User

_log = structlog.get_logger("auth_service.risk")

FREEZE_THRESHOLD = 2  # NFR-S6 "任 2 项触发"

R3_CODE = "ip_24_share"
R3_MIN_PRIOR_USERS = 3  # ≥3 prior distinct users on same /24 → trigger
R3_LOOKBACK_DAYS = 30


def _ip_to_24_network(ip_str: str) -> str | None:
    """Return the /24 network address string for an IPv4 input, else None."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return None
    if not isinstance(addr, ipaddress.IPv4Address):
        return None  # v1 covers IPv4 only; IPv6 deferred
    return str(ipaddress.ip_network(f"{ip_str}/24", strict=False))


async def evaluate_ip_24_share(
    session: AsyncSession,
    user_id: uuid.UUID,
    signup_ip: str | None,
) -> bool:
    """Return True iff the signup IP shares its /24 with >=R3_MIN_PRIOR_USERS distinct prior users.

    Empty/null/non-IPv4 signup_ip → False (no signal).
    """
    if signup_ip is None or signup_ip == "":
        return False
    net = _ip_to_24_network(signup_ip)
    if net is None:
        return False

    since = datetime.now(UTC) - timedelta(days=R3_LOOKBACK_DAYS)
    # Pull recent signup audit-log IPs as text and group in Python.
    # INET-native /24 grouping in SQL works but would couple to PG; this is simple + fast for v1 volumes.
    result = await session.execute(
        text(
            "SELECT DISTINCT user_id, host(ip_address)::text AS ip "
            "FROM audit_logs "
            "WHERE action = 'auth.signup' "
            "AND ip_address IS NOT NULL "
            "AND created_at >= :since "
            "AND user_id IS NOT NULL "
            "AND user_id != :uid"
        ),
        {"since": since, "uid": user_id},
    )
    distinct_prior_users: set[uuid.UUID] = set()
    for row in result:
        prior_net = _ip_to_24_network(row.ip)
        if prior_net == net:
            distinct_prior_users.add(row.user_id)

    return len(distinct_prior_users) >= R3_MIN_PRIOR_USERS


async def evaluate_signup(
    session: AsyncSession,
    user_id: uuid.UUID,
    signup_ip: str | None,
) -> list[str]:
    """Apply all ENABLED auto-rules at signup time.

    Returns list of triggered rule_codes. Caller persists flags + freezes
    via `apply_flags_and_maybe_freeze` (separated so admin paths can share
    the same sink).
    """
    triggered: list[str] = []

    # Check which rules are enabled before running their (potentially-expensive) checks.
    enabled = await _enabled_rule_codes(session)

    if R3_CODE in enabled:
        if await evaluate_ip_24_share(session, user_id, signup_ip):
            triggered.append(R3_CODE)

    # Future: when fingerprint_high / calls_24h_over_20 / payment_reused /
    # phone_reused enable, add their checks here as `if CODE in enabled: ...`.

    return triggered


async def _enabled_rule_codes(session: AsyncSession) -> set[str]:
    """Return the set of currently-enabled rule_codes."""
    result = await session.execute(select(RiskRule.code).where(RiskRule.enabled.is_(True)))
    return {row[0] for row in result.all()}


async def _distinct_enabled_triggers(session: AsyncSession, user_id: uuid.UUID) -> set[str]:
    """Return the distinct ENABLED rule_codes the user has been flagged for."""
    result = await session.execute(
        select(RiskFlag.rule_code)
        .join(RiskRule, RiskRule.code == RiskFlag.rule_code)
        .where(and_(RiskFlag.user_id == user_id, RiskRule.enabled.is_(True)))
        .distinct()
    )
    return {row[0] for row in result.all()}


async def apply_flags_and_maybe_freeze(
    session: AsyncSession,
    user_id: uuid.UUID,
    new_flags: list[tuple[str, str, dict[str, Any]]],
) -> bool:
    """Persist new_flags + freeze user when distinct ENABLED triggers >= FREEZE_THRESHOLD.

    `new_flags` is a list of (rule_code, source, metadata). source is
    'auto' (signup-time auto-detection) or 'admin' (manual flag from
    /v1/admin/risk-flags).

    Same-session writes; caller commits. Idempotent freeze (re-evaluating
    on an already-frozen user is a no-op UPDATE).

    Returns True iff the user transitioned to frozen by this call.

    Empty `new_flags` is supported: the admin endpoint inserts its own flag
    before calling here (so it can return the new flag's id), then passes
    `[]` to share this same freeze code-path.
    """
    if new_flags:
        for rule_code, source, metadata in new_flags:
            session.add(
                RiskFlag(
                    user_id=user_id,
                    rule_code=rule_code,
                    source=source,
                    flag_metadata=metadata,
                )
            )
        await session.flush()  # ensures the new flags are visible to the count below

    distinct_enabled = await _distinct_enabled_triggers(session, user_id)
    if len(distinct_enabled) < FREEZE_THRESHOLD:
        return False

    # Read current is_frozen to know if THIS call is the transition.
    cur = (
        await session.execute(select(User.is_frozen).where(User.id == user_id))
    ).scalar_one_or_none()
    if cur is True:
        return False  # already frozen — nothing new

    await session.execute(update(User).where(User.id == user_id).values(is_frozen=True))
    session.add(
        AuditLog(
            user_id=user_id,
            actor="system",
            action="user.freeze",
            resource_type="user",
            resource_id=user_id,
            audit_metadata={
                "event_kind": "freeze",
                "triggered_rules": sorted(distinct_enabled),
                "rule_count": len(distinct_enabled),
                "threshold": FREEZE_THRESHOLD,
            },
        )
    )
    _log.info(
        "risk.user.frozen",
        user_id=str(user_id),
        triggered_rules=sorted(distinct_enabled),
    )
    return True
