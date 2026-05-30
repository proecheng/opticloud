"""Billing HTTP routes (Story 5.A.1 + 5.A.4 + 5.A.5 + 5.A.6).

Endpoints (all require Bearer JWT or X-Internal-Service-Auth):
- GET  /v1/billing/balance               — read current credits balance (pure)
- POST /v1/billing/topups                — create pending topup request
- POST /v1/billing/topups/{id}/confirm   — internal payment-confirmation credit
- POST /v1/billing/charges/estimate      — 5.A.5: pre-charge guard preview
- POST /v1/billing/charges               — create a Saga + lazy-seed if first call (5.A.5: gates on `confirmed` when warnings exist)
- POST /v1/billing/charges/{id}/reserve  — 5.A.4: PENDING → RESERVED only
- POST /v1/billing/charges/{id}/finalize — 5.A.4: RESERVED → CHARGED (per-formula) or REFUNDED
- POST /v1/billing/charges/{id}/confirm  — DEPRECATED 5.A.1 (reserve + service_success in one)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from opticloud_shared.cost_telemetry import CostTelemetryEvent, CostUnit, record_cost_event
from opticloud_shared.errors import ErrorDetail, rfc7807_error
from prometheus_client import Counter
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from billing_service.auth_dep import require_internal_service, require_user
from billing_service.buckets import (
    ALL_BUCKETS,
    BUCKET_EXPIRES_HINT_ZH,
    BUCKET_LABELS_ZH,
    BUCKET_SIGNUP,
    BUCKET_TOPUP,
)
from billing_service.config import settings
from billing_service.db import get_session
from billing_service.exceptions import (
    CrossTenantKeyError,
    IdempotencyConflictError,
    InvalidSagaTransitionError,
    SagaNotFoundError,
    SagaTerminalError,
)
from billing_service.models import (
    BillingSubscription,
    CostAttribution,
    CreditTransaction,
    IdempotencyKeyRow,
    OutboxEvent,
    SagaInstance,
)
from billing_service.plans import PLANS, Plan, PlanCode, add_one_calendar_month, get_plan
from billing_service.pricing import classify_warnings, compute_charge_amount
from billing_service.saga_orchestrator import SagaOrchestrator, hash_body
from billing_service.schemas import (
    AutoRefundRequest,
    AutoRefundResponse,
    BalanceResponse,
    BucketBalance,
    ChargeCreateRequest,
    ChargeResponse,
    EduStarterSyncRequest,
    EstimateRequest,
    EstimateResponse,
    FinalizeChargeRequest,
    FinalizeChargeResponse,
    PlanListResponse,
    PlanRateLimits,
    PlanResponse,
    RefillDueRequest,
    RefillDueResponse,
    ReserveChargeResponse,
    SubscriptionCreateRequest,
    SubscriptionProrationResponse,
    SubscriptionResponse,
    TopupConfirmRequest,
    TopupCreateRequest,
    TopupResponse,
    WarningResponse,
    validate_idempotency_key,
)

billing_router = APIRouter(prefix="/v1/billing", tags=["billing"])
logger = logging.getLogger(__name__)

# SRE1 — Story 5.A.5: pre-charge guard observability
ESTIMATE_TOTAL: Counter = Counter(
    "billing_estimate_total",
    "POST /v1/billing/charges/estimate calls labelled by warning shape",
    ["warnings_kind"],
)


def _problem_response(
    *,
    title: str,
    status_code: int,
    detail: str,
    errors: list[ErrorDetail] | None = None,
) -> Response:
    """Typed wrapper around the shared RFC 7807 helper for strict mypy."""
    return cast(
        Response,
        rfc7807_error(
            title=title,
            status_code=status_code,
            detail=detail,
            errors=errors,
        ),
    )


async def _balance_for(session: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """Sum credit_transactions.amount for user; returns Decimal('0.00') if none."""
    stmt = select(func.coalesce(func.sum(CreditTransaction.amount), Decimal("0"))).where(
        CreditTransaction.user_id == user_id
    )
    result = await session.execute(stmt)
    total = result.scalar_one()
    return Decimal(str(total)).quantize(Decimal("0.0001"))


async def _balance_buckets_for(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Decimal]:
    """Per-bucket balance for a user (Story 5.A.2 FR B1).

    Always returns all 4 canonical bucket names; buckets with no rows get 0.
    """
    stmt = (
        select(CreditTransaction.bucket, func.sum(CreditTransaction.amount))
        .where(CreditTransaction.user_id == user_id)
        .group_by(CreditTransaction.bucket)
    )
    rows = (await session.execute(stmt)).all()
    by_bucket: dict[str, Decimal] = {row[0]: Decimal(str(row[1])) for row in rows}
    return {name: by_bucket.get(name, Decimal("0")) for name in ALL_BUCKETS}


async def _has_any_transactions(session: AsyncSession, user_id: uuid.UUID) -> bool:
    stmt = (
        select(func.count())
        .select_from(CreditTransaction)
        .where(CreditTransaction.user_id == user_id)
    )
    result = await session.execute(stmt)
    return bool(result.scalar_one())


async def _seed_demo_balance(session: AsyncSession, user_id: uuid.UUID) -> None:
    """A2: lazy-seed first-time user with J1 demo balance (POST only).

    Story 5.A.2: tagged as bucket="signup" so the dashboard shows the
    starter ¥50 in the 注册 bucket (not 月度).
    """
    seed_amount = Decimal(settings.j1_demo_seed_amount)
    session.add(
        CreditTransaction(
            user_id=user_id,
            saga_id=None,
            amount=seed_amount,
            kind="topup",
            bucket=BUCKET_SIGNUP,
            currency="CNY",
            metadata_json={"source": "j1_demo_seed"},
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()


def _topup_response(saga: SagaInstance, *, balance_after: Decimal | None = None) -> TopupResponse:
    amount = saga.amount or Decimal("0")
    return TopupResponse(
        topup_id=str(saga.id),
        current_state=saga.current_state,
        amount=f"{amount:.2f}",
        bucket="topup",
        expires_at=None,
        expires_hint=BUCKET_EXPIRES_HINT_ZH[BUCKET_TOPUP] or "永不过期",
        balance_after=f"{balance_after:.2f}" if balance_after is not None else None,
    )


def _plan_response(plan: Plan) -> PlanResponse:
    return PlanResponse(
        code=plan.code,
        label=plan.label,
        label_zh=plan.label_zh,
        monthly_credits=f"{plan.monthly_credits:.2f}",
        rate_limits=PlanRateLimits(
            rps=plan.rate_limits.rps,
            requests_per_minute=plan.rate_limits.requests_per_minute,
            concurrent_solves=plan.rate_limits.concurrent_solves,
            t5_t6_p5=plan.rate_limits.t5_t6_p5,
            custom=plan.rate_limits.custom,
        ),
        commercial_review_required=plan.commercial_review_required,
        external_payment_required=plan.external_payment_required,
    )


def _subscription_response(
    subscription: BillingSubscription,
    *,
    proration: SubscriptionProrationResponse | None = None,
) -> SubscriptionResponse:
    plan = get_plan(cast(PlanCode, subscription.plan_code))
    entitlement_source = _subscription_entitlement_source(subscription)
    refill_bucket = _subscription_refill_bucket(subscription)
    external_payment_required = _subscription_external_payment_required(subscription, plan)
    education_entitlement = _subscription_education_entitlement(subscription)
    trial_ends_at = _subscription_trial_ends_at(subscription)
    fallback_plan_code = _subscription_fallback_plan_code(subscription)
    return SubscriptionResponse(
        subscription_id=str(subscription.id),
        plan_code=plan.code,
        status=cast(Any, subscription.status),
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        monthly_credits=f"{plan.monthly_credits:.2f}",
        entitlement_source=entitlement_source,
        refill_bucket=refill_bucket,
        external_payment_required=external_payment_required,
        education_entitlement=education_entitlement,
        trial_ends_at=trial_ends_at,
        fallback_plan_code=fallback_plan_code,
        proration=proration,
    )


def _implicit_free_subscription_response() -> SubscriptionResponse:
    plan = get_plan("free")
    return SubscriptionResponse(
        subscription_id=None,
        plan_code=plan.code,
        status="implicit_free",
        current_period_start=None,
        current_period_end=None,
        monthly_credits=f"{plan.monthly_credits:.2f}",
        refill_bucket="monthly",
        external_payment_required=plan.external_payment_required,
    )


def _charge_saga_type(body: ChargeCreateRequest) -> str:
    return f"{body.purpose}_charge"


def _charge_payload(body: ChargeCreateRequest, *, include_confirmation_ref: bool) -> dict[str, str]:
    payload = {
        "reference_id": body.reference_id,
        "purpose": body.purpose,
    }
    if include_confirmation_ref:
        payload["confirmation_ref"] = "precharge-confirmed"
    return payload


def _charge_request_hash(body: ChargeCreateRequest, *, include_confirmation_ref: bool) -> str:
    return hash_body(
        {
            "saga_type": _charge_saga_type(body),
            "payload": _charge_payload(
                body,
                include_confirmation_ref=include_confirmation_ref,
            ),
            "amount": str(body.amount) if body.amount else None,
        }
    )


def _charge_request_hash_candidates(body: ChargeCreateRequest) -> set[str]:
    candidates = {_charge_request_hash(body, include_confirmation_ref=False)}
    if body.confirmed:
        candidates.add(_charge_request_hash(body, include_confirmation_ref=True))
    return candidates


def _charge_response_json(response: ChargeResponse) -> dict[str, Any]:
    return response.model_dump(mode="json")


def _subscription_response_json(response: SubscriptionResponse) -> dict[str, Any]:
    return response.model_dump(mode="json")


def _subscription_request_hash(body: SubscriptionCreateRequest) -> str:
    return hash_body({"operation": "subscription_create", "plan_code": body.plan_code})


def _edu_pro_trial_request_hash() -> str:
    return hash_body({"operation": "edu_pro_trial_activate"})


def _subscription_entitlement_source(subscription: BillingSubscription) -> str | None:
    raw = subscription.metadata_json.get("source")
    return raw if isinstance(raw, str) and raw == "edu_tier" else None


def _subscription_education_entitlement(subscription: BillingSubscription) -> str | None:
    if _subscription_entitlement_source(subscription) != "edu_tier":
        return None
    raw = subscription.metadata_json.get("education_entitlement")
    return raw if isinstance(raw, str) else None


def _subscription_is_edu_starter(subscription: BillingSubscription) -> bool:
    return (
        subscription.plan_code == "starter"
        and subscription.metadata_json.get("source") == "edu_tier"
        and subscription.metadata_json.get("education_entitlement") == "starter_free"
    )


def _subscription_is_edu_pro_trial(subscription: BillingSubscription) -> bool:
    return (
        subscription.plan_code == "pro"
        and subscription.metadata_json.get("source") == "edu_tier"
        and subscription.metadata_json.get("education_entitlement") == "pro_30d_trial"
    )


def _subscription_has_edu_entitlement(subscription: BillingSubscription) -> bool:
    return _subscription_education_entitlement(subscription) in {
        "starter_free",
        "pro_30d_trial",
    }


def _subscription_has_education_metadata(subscription: BillingSubscription) -> bool:
    return (
        subscription.metadata_json.get("source") == "edu_tier"
        or isinstance(subscription.metadata_json.get("education_entitlement"), str)
        or subscription.metadata_json.get("education_pro_trial_used") is True
    )


def _parse_metadata_datetime(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _subscription_trial_ends_at(subscription: BillingSubscription) -> datetime | None:
    if not _subscription_is_edu_pro_trial(subscription):
        return None
    return _parse_metadata_datetime(subscription.metadata_json.get("trial_ends_at"))


def _subscription_fallback_plan_code(
    subscription: BillingSubscription,
) -> Literal["starter"] | None:
    if not _subscription_is_edu_pro_trial(subscription):
        return None
    raw = subscription.metadata_json.get("fallback_plan_code")
    return "starter" if raw == "starter" else None


def _subscription_trial_used(subscription: BillingSubscription) -> bool:
    return bool(subscription.metadata_json.get("education_pro_trial_used") is True)


def _subscription_refill_bucket(
    subscription: BillingSubscription,
) -> Literal["monthly", "edu"]:
    return "edu" if _subscription_has_edu_entitlement(subscription) else "monthly"


def _subscription_external_payment_required(subscription: BillingSubscription, plan: Plan) -> bool:
    raw = subscription.metadata_json.get("external_payment_required")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.lower() == "true"
    if _subscription_has_edu_entitlement(subscription):
        return False
    return plan.external_payment_required


async def _idempotency_row_by_key(
    session: AsyncSession, idempotency_key: str
) -> IdempotencyKeyRow | None:
    return await session.get(IdempotencyKeyRow, idempotency_key)


async def _persist_charge_response_body(
    session: AsyncSession,
    idempotency_key: str,
    response: ChargeResponse,
) -> None:
    row = await _idempotency_row_by_key(session, idempotency_key)
    if row is None:
        raise RuntimeError(f"idempotency row {idempotency_key!r} missing after Saga start")
    row.response_body = _charge_response_json(response)
    await session.flush()


async def _active_subscription_for(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> BillingSubscription | None:
    stmt = select(BillingSubscription).where(
        BillingSubscription.user_id == user_id,
        BillingSubscription.status == "active",
    )
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def _lock_user_for_subscription(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Serialize first-subscription creation per user without a billing-side User model."""
    await session.execute(
        text("SELECT id FROM users WHERE id = :user_id FOR UPDATE"), {"user_id": user_id}
    )


async def _user_is_edu_tier(session: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await session.execute(
        text("SELECT edu_tier FROM users WHERE id = :user_id"), {"user_id": user_id}
    )
    return bool(result.scalar_one_or_none())


async def _has_edu_signup_seed(session: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await session.execute(
        text(
            """
            SELECT COUNT(*)
              FROM credit_transactions
             WHERE user_id = :user_id
               AND bucket = 'edu'
               AND metadata ->> 'source' = 'edu_tier_signup'
            """
        ),
        {"user_id": user_id},
    )
    return bool(result.scalar_one())


def _edu_starter_metadata(existing: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        **(existing or {}),
        "source": "edu_tier",
        "education_entitlement": "starter_free",
        "external_payment_required": False,
    }


def _edu_pro_trial_metadata(
    existing: dict[str, Any] | None,
    *,
    trial_start: datetime,
    trial_end: datetime,
) -> dict[str, Any]:
    trial_start_text = trial_start.isoformat()
    trial_end_text = trial_end.isoformat()
    metadata = {
        **(existing or {}),
        "source": "edu_tier",
        "education_entitlement": "pro_30d_trial",
        "education_pro_trial_used": True,
        "trial_started_at": trial_start_text,
        "trial_ends_at": trial_end_text,
        "education_pro_trial_started_at": trial_start_text,
        "education_pro_trial_ends_at": trial_end_text,
        "fallback_plan_code": "starter",
        "fallback_entitlement": "starter_free",
        "external_payment_required": False,
    }
    return metadata


def _edu_starter_fallback_metadata(existing: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = _edu_starter_metadata(existing)
    metadata.pop("trial_started_at", None)
    metadata.pop("trial_ends_at", None)
    metadata.pop("fallback_plan_code", None)
    metadata.pop("fallback_entitlement", None)
    return metadata


def _ceil_days(delta: timedelta) -> int:
    total_microseconds = (
        delta.days * 24 * 60 * 60 + delta.seconds
    ) * 1_000_000 + delta.microseconds
    if total_microseconds <= 0:
        return 0
    day_microseconds = 24 * 60 * 60 * 1_000_000
    return (total_microseconds + day_microseconds - 1) // day_microseconds


def _subscription_proration_response(
    *,
    from_plan_code: PlanCode,
    to_plan_code: PlanCode,
    amount: Decimal,
    remaining_days: int,
    total_days: int,
) -> SubscriptionProrationResponse:
    return SubscriptionProrationResponse(
        from_plan_code=from_plan_code,
        to_plan_code=to_plan_code,
        amount=f"{amount:.2f}",
        currency="CNY",
        remaining_days=remaining_days,
        total_days=total_days,
    )


def _subscription_proration_metadata(
    subscription: BillingSubscription,
    *,
    from_plan_code: PlanCode,
    to_plan_code: PlanCode,
    amount: Decimal,
    prorated_at: datetime,
    remaining_days: int,
    total_days: int,
    monthly_credit_delta: Decimal,
) -> dict[str, str]:
    return {
        "subscription_id": str(subscription.id),
        "from_plan_code": from_plan_code,
        "to_plan_code": to_plan_code,
        "period_start": subscription.current_period_start.isoformat(),
        "period_end": subscription.current_period_end.isoformat(),
        "prorated_at": prorated_at.isoformat(),
        "remaining_days": str(remaining_days),
        "total_days": str(total_days),
        "monthly_credit_delta": f"{monthly_credit_delta:.2f}",
        "amount": f"{amount:.2f}",
        "trigger": "plan_upgrade_proration",
        "bucket": "monthly",
    }


def _subscription_payload(subscription: BillingSubscription) -> dict[str, str]:
    education_entitlement = _subscription_education_entitlement(subscription)
    return {
        "subscription_id": str(subscription.id),
        "plan_code": subscription.plan_code,
        "status": subscription.status,
        "period_start": subscription.current_period_start.isoformat(),
        "period_end": subscription.current_period_end.isoformat(),
        "refill_bucket": _subscription_refill_bucket(subscription),
        **({"entitlement_source": "edu_tier"} if education_entitlement is not None else {}),
        **({"education_entitlement": education_entitlement} if education_entitlement else {}),
    }


async def _write_subscription_outbox(
    session: AsyncSession,
    *,
    subscription: BillingSubscription,
    event_type: str,
    payload_extra: dict[str, str] | None = None,
) -> None:
    session.add(
        OutboxEvent(
            aggregate_type="billing_subscription",
            aggregate_id=subscription.id,
            event_type=event_type,
            event_version=1,
            payload={
                **_subscription_payload(subscription),
                **(payload_extra or {}),
            },
            headers={"compensation": "none"},
            occurred_at=datetime.now(UTC),
        )
    )


def _subscription_refill_metadata(
    subscription: BillingSubscription, *, trigger: str
) -> dict[str, str]:
    education_entitlement = _subscription_education_entitlement(subscription)
    return {
        "subscription_id": str(subscription.id),
        "plan_code": subscription.plan_code,
        "period_start": subscription.current_period_start.isoformat(),
        "period_end": subscription.current_period_end.isoformat(),
        "trigger": trigger,
        "bucket": _subscription_refill_bucket(subscription),
        **({"entitlement_source": "edu_tier"} if education_entitlement is not None else {}),
        **({"education_entitlement": education_entitlement} if education_entitlement else {}),
    }


async def _apply_monthly_refill_once(
    session: AsyncSession,
    subscription: BillingSubscription,
    *,
    trigger: str,
) -> bool:
    """Write the monthly refill row for the current period if not already applied."""
    if subscription.last_refilled_period_start == subscription.current_period_start:
        return False

    plan = get_plan(cast(PlanCode, subscription.plan_code))
    now = datetime.now(UTC)
    subscription.last_refilled_period_start = subscription.current_period_start
    subscription.updated_at = now
    if plan.monthly_credits <= Decimal("0"):
        await session.flush()
        return False
    refill_bucket = _subscription_refill_bucket(subscription)

    session.add(
        CreditTransaction(
            user_id=subscription.user_id,
            saga_id=None,
            amount=plan.monthly_credits,
            kind="monthly_refill",
            bucket=refill_bucket,
            currency="CNY",
            metadata_json=_subscription_refill_metadata(subscription, trigger=trigger),
            created_at=now,
        )
    )
    await _write_subscription_outbox(
        session,
        subscription=subscription,
        event_type="billing.subscription.refilled",
        payload_extra={
            "amount": f"{plan.monthly_credits:.2f}",
            "bucket": refill_bucket,
            "trigger": trigger,
        },
    )
    await session.flush()
    return True


async def _upgrade_starter_to_pro_with_proration(
    session: AsyncSession,
    subscription: BillingSubscription,
    *,
    now: datetime,
) -> Response | SubscriptionResponse:
    if _subscription_has_education_metadata(subscription):
        await session.rollback()
        return _problem_response(
            title="Plan change deferred",
            status_code=status.HTTP_409_CONFLICT,
            detail="education plan changes are handled by dedicated education subscription flows",
        )
    if await _user_is_edu_tier(session, subscription.user_id):
        await session.rollback()
        return _problem_response(
            title="Plan change deferred",
            status_code=status.HTTP_409_CONFLICT,
            detail="education users must use education subscription flows",
        )
    if subscription.current_period_end <= now:
        await session.rollback()
        return _problem_response(
            title="Subscription period already due",
            status_code=status.HTTP_409_CONFLICT,
            detail="run subscription refill-due before prorating an upgrade",
        )

    from_plan_code: PlanCode = "starter"
    to_plan_code: PlanCode = "pro"
    from_plan = get_plan(from_plan_code)
    to_plan = get_plan(to_plan_code)
    total_days = _ceil_days(subscription.current_period_end - subscription.current_period_start)
    remaining_days = _ceil_days(subscription.current_period_end - now)
    if total_days <= 0 or remaining_days <= 0:
        await session.rollback()
        return _problem_response(
            title="Invalid subscription period",
            status_code=status.HTTP_409_CONFLICT,
            detail="subscription period cannot be prorated",
        )

    monthly_credit_delta = to_plan.monthly_credits - from_plan.monthly_credits
    amount = (monthly_credit_delta * Decimal(remaining_days) / Decimal(total_days)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if amount <= Decimal("0.00"):
        await session.rollback()
        return _problem_response(
            title="Invalid proration amount",
            status_code=status.HTTP_409_CONFLICT,
            detail="subscription upgrade produced no positive prorated adjustment",
        )

    subscription.plan_code = to_plan_code
    subscription.updated_at = now
    metadata = _subscription_proration_metadata(
        subscription,
        from_plan_code=from_plan_code,
        to_plan_code=to_plan_code,
        amount=amount,
        prorated_at=now,
        remaining_days=remaining_days,
        total_days=total_days,
        monthly_credit_delta=monthly_credit_delta,
    )
    session.add(
        CreditTransaction(
            user_id=subscription.user_id,
            saga_id=None,
            amount=amount,
            kind="subscription_proration",
            bucket="monthly",
            currency="CNY",
            metadata_json=metadata,
            created_at=now,
        )
    )
    await _write_subscription_outbox(
        session,
        subscription=subscription,
        event_type="billing.subscription.plan_changed",
        payload_extra={
            "from_plan_code": from_plan_code,
            "to_plan_code": to_plan_code,
            "proration_amount": f"{amount:.2f}",
            "currency": "CNY",
            "remaining_days": str(remaining_days),
            "total_days": str(total_days),
            "trigger": "plan_upgrade_proration",
        },
    )
    await session.flush()
    proration = _subscription_proration_response(
        from_plan_code=from_plan_code,
        to_plan_code=to_plan_code,
        amount=amount,
        remaining_days=remaining_days,
        total_days=total_days,
    )
    return _subscription_response(subscription, proration=proration)


async def _subscription_replay_response_if_cached(
    session: AsyncSession,
    *,
    body: SubscriptionCreateRequest,
    user_id: uuid.UUID,
    idempotency_key: str,
) -> Response | SubscriptionResponse | None:
    row = await _idempotency_row_by_key(session, idempotency_key)
    if row is None or row.expires_at <= datetime.now(UTC):
        return None

    if row.user_id != user_id:
        owner_user_id = row.user_id
        await session.rollback()
        return _problem_response(
            title="Cross-tenant key reuse forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Idempotency key {idempotency_key!r} belongs to tenant "
                f"{owner_user_id}, not {user_id}"
            ),
        )

    if row.request_body_hash != _subscription_request_hash(body):
        await session.rollback()
        return _problem_response(
            title="Idempotency Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key was reused with a different request body",
        )

    if row.response_body is not None:
        return SubscriptionResponse.model_validate(row.response_body)

    subscription = await _active_subscription_for(session, user_id)
    if subscription is None:
        await session.rollback()
        return _problem_response(
            title="Subscription Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail="idempotency row is not linked to an active subscription",
        )
    response = _subscription_response(subscription)
    row.response_body = _subscription_response_json(response)
    await session.commit()
    return response


async def _edu_pro_trial_replay_response_if_cached(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    idempotency_key: str,
) -> Response | SubscriptionResponse | None:
    row = await _idempotency_row_by_key(session, idempotency_key)
    if row is None or row.expires_at <= datetime.now(UTC):
        return None

    if row.user_id != user_id:
        owner_user_id = row.user_id
        await session.rollback()
        return _problem_response(
            title="Cross-tenant key reuse forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Idempotency key {idempotency_key!r} belongs to tenant "
                f"{owner_user_id}, not {user_id}"
            ),
        )

    if row.request_body_hash != _edu_pro_trial_request_hash():
        await session.rollback()
        return _problem_response(
            title="Idempotency Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key was reused with a different request body",
        )

    if row.response_body is not None:
        return SubscriptionResponse.model_validate(row.response_body)

    subscription = await _active_subscription_for(session, user_id)
    if subscription is None or not _subscription_is_edu_pro_trial(subscription):
        await session.rollback()
        return _problem_response(
            title="Subscription Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail="idempotency row is not linked to an active education Pro trial",
        )
    response = _subscription_response(subscription)
    row.response_body = _subscription_response_json(response)
    await session.commit()
    return response


async def _activate_or_return_edu_starter(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    passthrough_non_starter: bool = True,
) -> Response | SubscriptionResponse:
    await _lock_user_for_subscription(session, user_id)
    if not await _user_is_edu_tier(session, user_id):
        await session.rollback()
        return _problem_response(
            title="Education entitlement not available",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user is not eligible for education Starter",
        )

    active = await _active_subscription_for(session, user_id, for_update=True)
    now = datetime.now(UTC)
    has_signup_seed = await _has_edu_signup_seed(session, user_id)
    activation_needed = False
    should_apply_initial_refill = False

    if active is not None:
        if _subscription_is_edu_starter(active):
            return _subscription_response(active)

        if active.plan_code == "starter":
            active.metadata_json = _edu_starter_metadata(active.metadata_json)
            active.updated_at = now
            await _write_subscription_outbox(
                session,
                subscription=active,
                event_type="billing.subscription.edu_starter.activated",
            )
            await session.flush()
            return _subscription_response(active)

        if active.plan_code == "free":
            active.plan_code = "starter"
            active.current_period_start = now
            active.current_period_end = add_one_calendar_month(now)
            active.last_refilled_period_start = now if has_signup_seed else None
            active.metadata_json = _edu_starter_metadata(active.metadata_json)
            active.updated_at = now
            activation_needed = True
            should_apply_initial_refill = not has_signup_seed
            subscription = active
        elif passthrough_non_starter:
            return _subscription_response(active)
        else:
            await session.rollback()
            return _problem_response(
                title="Plan change deferred",
                status_code=status.HTTP_409_CONFLICT,
                detail="plan upgrade/downgrade with proration is handled by Story 5.B.4",
            )
    else:
        subscription = BillingSubscription(
            user_id=user_id,
            plan_code="starter",
            status="active",
            current_period_start=now,
            current_period_end=add_one_calendar_month(now),
            last_refilled_period_start=now if has_signup_seed else None,
            metadata_json=_edu_starter_metadata(),
            created_at=now,
            updated_at=now,
        )
        session.add(subscription)
        activation_needed = True
        should_apply_initial_refill = not has_signup_seed

    await session.flush()
    if activation_needed:
        await _write_subscription_outbox(
            session,
            subscription=subscription,
            event_type="billing.subscription.edu_starter.activated",
        )
    if should_apply_initial_refill:
        await _apply_monthly_refill_once(session, subscription, trigger="activation")
    return _subscription_response(subscription)


async def _upsert_edu_pro_trial_idempotency_row(
    session: AsyncSession,
    *,
    idempotency_key: str,
    user_id: uuid.UUID,
    response: SubscriptionResponse,
) -> None:
    now = datetime.now(UTC)
    expires_at = now + settings.saga_idempotency_ttl_hours * timedelta(hours=1)
    existing = await _idempotency_row_by_key(session, idempotency_key)
    if existing is not None:
        existing.user_id = user_id
        existing.request_body_hash = _edu_pro_trial_request_hash()
        existing.response_body = _subscription_response_json(response)
        existing.saga_id = None
        existing.expires_at = expires_at
        existing.created_at = now
        await session.flush()
        return

    session.add(
        IdempotencyKeyRow(
            key=idempotency_key,
            user_id=user_id,
            request_body_hash=_edu_pro_trial_request_hash(),
            response_body=_subscription_response_json(response),
            saga_id=None,
            expires_at=expires_at,
            created_at=now,
        )
    )
    await session.flush()


async def _activate_or_return_edu_pro_trial(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> Response | SubscriptionResponse:
    await _lock_user_for_subscription(session, user_id)
    if not await _user_is_edu_tier(session, user_id):
        await session.rollback()
        return _problem_response(
            title="Education entitlement not available",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user is not eligible for education Pro trial",
        )

    active = await _active_subscription_for(session, user_id, for_update=True)
    if active is not None:
        if _subscription_is_edu_pro_trial(active):
            return _subscription_response(active)
        if _subscription_trial_used(active):
            await session.rollback()
            return _problem_response(
                title="Education Pro trial already used",
                status_code=status.HTTP_409_CONFLICT,
                detail="education Pro trial can only be activated once",
            )
        if active.plan_code in {"pro", "team", "enterprise"}:
            await session.rollback()
            return _problem_response(
                title="Plan change deferred",
                status_code=status.HTTP_409_CONFLICT,
                detail="plan upgrade/downgrade with proration is handled by Story 5.B.4",
            )

    now = datetime.now(UTC)
    trial_end = now + timedelta(days=30)
    if active is None:
        subscription = BillingSubscription(
            user_id=user_id,
            plan_code="pro",
            status="active",
            current_period_start=now,
            current_period_end=trial_end,
            last_refilled_period_start=None,
            metadata_json=_edu_pro_trial_metadata(None, trial_start=now, trial_end=trial_end),
            created_at=now,
            updated_at=now,
        )
        session.add(subscription)
    else:
        active.plan_code = "pro"
        active.current_period_start = now
        active.current_period_end = trial_end
        active.last_refilled_period_start = None
        active.metadata_json = _edu_pro_trial_metadata(
            active.metadata_json, trial_start=now, trial_end=trial_end
        )
        active.updated_at = now
        subscription = active

    await session.flush()
    await _write_subscription_outbox(
        session,
        subscription=subscription,
        event_type="billing.subscription.edu_pro_trial.activated",
        payload_extra={
            "trial_started_at": now.isoformat(),
            "trial_ends_at": trial_end.isoformat(),
            "fallback_plan_code": "starter",
        },
    )
    await _apply_monthly_refill_once(session, subscription, trigger="edu_pro_trial_activation")
    return _subscription_response(subscription)


async def _fallback_edu_pro_trial_to_starter(
    session: AsyncSession,
    subscription: BillingSubscription,
) -> bool:
    if not _subscription_is_edu_pro_trial(subscription):
        return False

    fallback_start = subscription.current_period_end
    fallback_end = add_one_calendar_month(fallback_start)
    subscription.plan_code = "starter"
    subscription.current_period_start = fallback_start
    subscription.current_period_end = fallback_end
    subscription.last_refilled_period_start = None
    subscription.metadata_json = _edu_starter_fallback_metadata(subscription.metadata_json)
    subscription.updated_at = datetime.now(UTC)
    await session.flush()
    await _write_subscription_outbox(
        session,
        subscription=subscription,
        event_type="billing.subscription.edu_pro_trial.ended",
        payload_extra={
            "ended_plan_code": "pro",
            "ended_education_entitlement": "pro_30d_trial",
            "trial_ended_at": fallback_start.isoformat(),
            "fallback_plan_code": "starter",
        },
    )
    await _write_subscription_outbox(
        session,
        subscription=subscription,
        event_type="billing.subscription.edu_starter.activated",
        payload_extra={"trigger": "edu_pro_trial_fallback"},
    )
    await _apply_monthly_refill_once(session, subscription, trigger="edu_pro_trial_fallback")
    return True


async def _legacy_charge_response_from_idempotency_row(
    session: AsyncSession,
    row: IdempotencyKeyRow,
) -> Response | ChargeResponse:
    if row.saga_id is None:
        await session.rollback()
        return _problem_response(
            title="Idempotency Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key is not linked to a charge Saga",
        )

    saga_id = row.saga_id
    saga = await session.get(SagaInstance, saga_id)
    if saga is None:
        await session.rollback()
        return _problem_response(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"charge {saga_id} not found",
        )

    balance = await _balance_for(session, row.user_id)
    response = ChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        amount=f"{saga.amount:.2f}" if saga.amount is not None else "0.00",
        currency="CNY",
        balance_before=f"{balance:.2f}",
        balance_after=f"{balance:.2f}",
    )
    row.response_body = _charge_response_json(response)
    await session.commit()
    return response


async def _charge_replay_response_if_cached(
    session: AsyncSession,
    *,
    body: ChargeCreateRequest,
    user_id: uuid.UUID,
    idempotency_key: str,
) -> Response | ChargeResponse | None:
    row = await _idempotency_row_by_key(session, idempotency_key)
    if row is None or row.expires_at <= datetime.now(UTC):
        return None

    if row.user_id != user_id:
        owner_user_id = row.user_id
        await session.rollback()
        return _problem_response(
            title="Cross-tenant key reuse forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Idempotency key {idempotency_key!r} belongs to tenant "
                f"{owner_user_id}, not {user_id}"
            ),
        )

    if row.request_body_hash not in _charge_request_hash_candidates(body):
        await session.rollback()
        return _problem_response(
            title="Idempotency Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key was reused with a different request body",
        )

    if row.response_body is not None:
        return ChargeResponse.model_validate(row.response_body)

    return await _legacy_charge_response_from_idempotency_row(session, row)


async def _topup_ledger_rows(session: AsyncSession, topup_id: uuid.UUID) -> list[CreditTransaction]:
    stmt = select(CreditTransaction).where(
        CreditTransaction.saga_id == topup_id,
        CreditTransaction.kind == "topup",
        CreditTransaction.bucket == BUCKET_TOPUP,
    )
    return list((await session.execute(stmt)).scalars().all())


def _ledger_payment_ref(row: CreditTransaction) -> str | None:
    raw = row.metadata_json.get("payment_ref")
    return raw if isinstance(raw, str) else None


def _classify_with_settings(estimated: Decimal, balance: Decimal) -> list[WarningResponse]:
    """Run classify_warnings with current config thresholds; convert to response shape."""
    warnings = classify_warnings(
        estimated_amount=estimated,
        balance=balance,
        p5_call_threshold=settings.p5_call_threshold,
        balance_low_ratio=settings.balance_low_ratio,
    )
    return [
        WarningResponse(
            kind=w.kind,  # type: ignore[arg-type]
            message=w.message,
            remediation_hint_key=w.remediation_hint_key,
        )
        for w in warnings
    ]


@billing_router.get("/plans", response_model=PlanListResponse)
async def list_plans(
    _user_id: uuid.UUID = Depends(require_user),
) -> PlanListResponse:
    """Story 5.B.1 — stable five-plan catalog."""
    return PlanListResponse(items=[_plan_response(plan) for plan in PLANS])


@billing_router.get("/subscriptions/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionResponse:
    """Pure read: no implicit row or ledger mutation for Free."""
    subscription = await _active_subscription_for(session, user_id)
    if subscription is None:
        return _implicit_free_subscription_response()
    return _subscription_response(subscription)


@billing_router.post(
    "/subscriptions/edu-starter/sync",
    response_model=SubscriptionResponse,
)
async def sync_edu_starter_subscription(
    body: EduStarterSyncRequest,
    _internal: None = Depends(require_internal_service),
    session: AsyncSession = Depends(get_session),
) -> Response | SubscriptionResponse:
    """Story 5.B.2 — materialize education Starter entitlement from users.edu_tier."""
    try:
        user_id = uuid.UUID(body.user_id)
    except ValueError:
        return _problem_response(
            title="Invalid user id",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id must be a UUID",
        )
    response = await _activate_or_return_edu_starter(session, user_id=user_id)
    if isinstance(response, Response):
        return response
    await session.commit()
    return response


@billing_router.post(
    "/subscriptions/edu-pro-trial",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def activate_edu_pro_trial_subscription(
    request: Request,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Response | SubscriptionResponse:
    """Story 5.B.3 — activate one education Pro 30-day trial for current user."""
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if (await request.body()).strip():
        return _problem_response(
            title="Request body not allowed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="education Pro trial activation uses the authenticated user only",
        )

    cached_response = await _edu_pro_trial_replay_response_if_cached(
        session,
        user_id=user_id,
        idempotency_key=idempotency_key,
    )
    if cached_response is not None:
        return cached_response

    response = await _activate_or_return_edu_pro_trial(session, user_id=user_id)
    if isinstance(response, Response):
        return response
    await _upsert_edu_pro_trial_idempotency_row(
        session,
        idempotency_key=idempotency_key,
        user_id=user_id,
        response=response,
    )
    await session.commit()
    return response


@billing_router.post(
    "/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    body: SubscriptionCreateRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Response | SubscriptionResponse:
    """Story 5.B.1 — create first active subscription and initial monthly refill."""
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    cached_response = await _subscription_replay_response_if_cached(
        session,
        body=body,
        user_id=user_id,
        idempotency_key=idempotency_key,
    )
    if cached_response is not None:
        return cached_response

    if body.plan_code == "starter" and await _user_is_edu_tier(session, user_id):
        edu_response = await _activate_or_return_edu_starter(
            session, user_id=user_id, passthrough_non_starter=False
        )
        if isinstance(edu_response, Response):
            return edu_response
        await _upsert_subscription_idempotency_row(
            session,
            idempotency_key=idempotency_key,
            user_id=user_id,
            body=body,
            response=edu_response,
        )
        await session.commit()
        return edu_response

    await _lock_user_for_subscription(session, user_id)
    active = await _active_subscription_for(session, user_id, for_update=True)
    if active is not None:
        response = _subscription_response(active)
        if active.plan_code != body.plan_code:
            if active.plan_code == "starter" and body.plan_code == "pro":
                upgrade_response = await _upgrade_starter_to_pro_with_proration(
                    session,
                    active,
                    now=datetime.now(UTC),
                )
                if isinstance(upgrade_response, Response):
                    return upgrade_response
                await _upsert_subscription_idempotency_row(
                    session,
                    idempotency_key=idempotency_key,
                    user_id=user_id,
                    body=body,
                    response=upgrade_response,
                )
                await session.commit()
                return upgrade_response

            await session.rollback()
            return _problem_response(
                title="Plan change deferred",
                status_code=status.HTTP_409_CONFLICT,
                detail="plan upgrade/downgrade with proration is handled by Story 5.B.4",
            )

        await _upsert_subscription_idempotency_row(
            session,
            idempotency_key=idempotency_key,
            user_id=user_id,
            body=body,
            response=response,
        )
        await session.commit()
        return response

    plan = get_plan(body.plan_code)
    now = datetime.now(UTC)
    subscription = BillingSubscription(
        user_id=user_id,
        plan_code=plan.code,
        status="active",
        current_period_start=now,
        current_period_end=add_one_calendar_month(now),
        last_refilled_period_start=None,
        metadata_json={
            "source": "user_subscription",
            "external_payment_required": str(plan.external_payment_required).lower(),
        },
        created_at=now,
        updated_at=now,
    )
    session.add(subscription)
    await session.flush()

    await _write_subscription_outbox(
        session,
        subscription=subscription,
        event_type="billing.subscription.activated",
    )
    await _apply_monthly_refill_once(session, subscription, trigger="activation")
    response = _subscription_response(subscription)
    await _upsert_subscription_idempotency_row(
        session,
        idempotency_key=idempotency_key,
        user_id=user_id,
        body=body,
        response=response,
    )

    await session.commit()
    return response


async def _upsert_subscription_idempotency_row(
    session: AsyncSession,
    *,
    idempotency_key: str,
    user_id: uuid.UUID,
    body: SubscriptionCreateRequest,
    response: SubscriptionResponse,
) -> None:
    now = datetime.now(UTC)
    expires_at = now + settings.saga_idempotency_ttl_hours * timedelta(hours=1)
    existing = await _idempotency_row_by_key(session, idempotency_key)
    if existing is not None:
        existing.user_id = user_id
        existing.request_body_hash = _subscription_request_hash(body)
        existing.response_body = _subscription_response_json(response)
        existing.saga_id = None
        existing.expires_at = expires_at
        existing.created_at = now
        await session.flush()
        return

    session.add(
        IdempotencyKeyRow(
            key=idempotency_key,
            user_id=user_id,
            request_body_hash=_subscription_request_hash(body),
            response_body=_subscription_response_json(response),
            saga_id=None,
            expires_at=expires_at,
            created_at=now,
        )
    )
    await session.flush()


@billing_router.post(
    "/subscriptions/refill-due",
    response_model=RefillDueResponse,
)
async def refill_due_subscriptions(
    body: RefillDueRequest,
    _internal: None = Depends(require_internal_service),
    session: AsyncSession = Depends(get_session),
) -> RefillDueResponse:
    """Internal scheduler path: refill due active subscriptions once per period."""
    as_of = body.as_of or datetime.now(UTC)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    stmt = (
        select(BillingSubscription)
        .where(
            BillingSubscription.status == "active",
            BillingSubscription.current_period_end <= as_of,
        )
        .with_for_update()
    )
    due = list((await session.execute(stmt)).scalars().all())
    processed = 0
    refilled = 0
    skipped_zero_credit = 0
    for subscription in due:
        processed += 1
        if _subscription_is_edu_pro_trial(subscription):
            await _fallback_edu_pro_trial_to_starter(session, subscription)
            refilled += 1
        while subscription.current_period_end <= as_of:
            subscription.current_period_start = subscription.current_period_end
            subscription.current_period_end = add_one_calendar_month(
                subscription.current_period_start
            )
            did_refill = await _apply_monthly_refill_once(
                session, subscription, trigger="scheduled_refill"
            )
            if did_refill:
                refilled += 1
            else:
                skipped_zero_credit += 1

    await session.commit()
    return RefillDueResponse(
        processed=processed,
        refilled=refilled,
        skipped_zero_credit=skipped_zero_credit,
        as_of=as_of,
    )


@billing_router.post(
    "/charges/estimate",
    response_model=EstimateResponse,
)
async def estimate_charge(
    body: EstimateRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> EstimateResponse:
    """Story 5.A.5 — pre-charge guard preview.

    Pure read: no Saga, no seeding, no ledger write. Returns the estimated max
    amount, current balance, and 0-1 warnings based on the pre-charge guard
    rules in config (p5_call_threshold + balance_low_ratio).

    `purpose` is ignored for amount computation in v1 (LP-only pricing) but
    persisted in the metric label so M3 analytics can split by call type.
    """
    estimated = Decimal(str(body.max_solve_seconds)) * settings.lp_rate_per_second
    balance = await _balance_for(session, user_id)
    warnings = _classify_with_settings(estimated, balance)

    metric_label = warnings[0].kind if warnings else "none"
    ESTIMATE_TOTAL.labels(warnings_kind=metric_label).inc()

    return EstimateResponse(
        estimated_amount=f"{estimated:.2f}",
        currency="CNY",
        balance=f"{balance:.2f}",
        warnings=warnings,
        requires_explicit_confirm=bool(warnings),
    )


@billing_router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> BalanceResponse:
    """Story 5.A.1 AC2 + 5.A.2 FR B1: pure read — no seeding side effect.

    Returns total balance + 4-bucket breakdown (always all 4 buckets, zero if empty).
    """
    balance = await _balance_for(session, user_id)
    by_bucket = await _balance_buckets_for(session, user_id)
    last_stmt = (
        select(CreditTransaction.created_at)
        .where(CreditTransaction.user_id == user_id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(1)
    )
    last = (await session.execute(last_stmt)).scalar_one_or_none()

    buckets_resp = [
        BucketBalance(
            name=name,  # type: ignore[arg-type]
            label_zh=BUCKET_LABELS_ZH[name],
            balance=f"{by_bucket[name]:.2f}",
            expires_hint=BUCKET_EXPIRES_HINT_ZH[name],
        )
        for name in ALL_BUCKETS
    ]
    return BalanceResponse(
        user_id=str(user_id),
        balance=f"{balance:.2f}",
        currency="CNY",
        last_transaction_at=last,
        buckets=buckets_resp,
    )


@billing_router.post("/topups", response_model=TopupResponse, status_code=status.HTTP_201_CREATED)
async def create_topup(
    body: TopupCreateRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Response | TopupResponse:
    """Story 5.A.6 — create an idempotent pending topup request.

    This public route never credits the ledger. Credits are written only by the
    internal payment-confirmation route after a trusted payment callback.
    """
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    orch = SagaOrchestrator(session)
    try:
        saga = await orch.start(
            saga_type="topup",
            user_id=user_id,
            idempotency_key=idempotency_key,
            payload={
                "reference_id": body.reference_id,
                "purpose": "topup",
            },
            amount=body.amount,
        )
    except CrossTenantKeyError as e:
        await session.rollback()
        return _problem_response(
            title="Cross-tenant key reuse forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except IdempotencyConflictError as e:
        await session.rollback()
        return _problem_response(
            title="Idempotency Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    await session.commit()
    return _topup_response(saga)


@billing_router.post("/topups/{topup_id}/confirm", response_model=TopupResponse)
async def confirm_topup(
    topup_id: uuid.UUID,
    body: TopupConfirmRequest,
    _internal: None = Depends(require_internal_service),
    session: AsyncSession = Depends(get_session),
) -> Response | TopupResponse:
    """Story 5.A.6 — internal payment confirmation writes topup Credits once."""
    stmt = select(SagaInstance).where(SagaInstance.id == topup_id).with_for_update()
    saga = (await session.execute(stmt)).scalar_one_or_none()
    if saga is None or saga.saga_type != "topup":
        await session.rollback()
        return _problem_response(
            title="Topup Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"topup {topup_id} not found",
        )

    amount = saga.amount or Decimal("0")
    existing_rows = await _topup_ledger_rows(session, topup_id)
    if existing_rows:
        existing_ref = _ledger_payment_ref(existing_rows[0])
        if existing_ref != body.payment_ref:
            await session.rollback()
            return _problem_response(
                title="Payment Reference Conflict",
                status_code=status.HTTP_409_CONFLICT,
                detail="topup has already been confirmed with a different payment_ref",
            )
        balance_after = await _balance_for(session, saga.user_id)
        return _topup_response(saga, balance_after=balance_after)

    if saga.current_state != "pending":
        await session.rollback()
        return _problem_response(
            title="Topup Already Finalized",
            status_code=status.HTTP_409_CONFLICT,
            detail=f"topup is already {saga.current_state}",
        )

    now = datetime.now(UTC)
    saga.current_state = "completed"
    saga.updated_at = now
    session.add(
        CreditTransaction(
            user_id=saga.user_id,
            saga_id=saga.id,
            amount=amount,
            kind="topup",
            bucket=BUCKET_TOPUP,
            currency="CNY",
            metadata_json={
                "provider": body.provider,
                "payment_ref": body.payment_ref,
                "expires_at": None,
            },
            created_at=now,
        )
    )
    session.add(
        OutboxEvent(
            aggregate_type="saga_instance",
            aggregate_id=saga.id,
            event_type="billing.topup.confirmed",
            event_version=1,
            payload={
                "saga_id": str(saga.id),
                "saga_type": saga.saga_type,
                "to_state": saga.current_state,
                "bucket": BUCKET_TOPUP,
                "provider": body.provider,
                "payment_ref": body.payment_ref,
            },
            headers={"compensation": "none"},
            occurred_at=now,
        )
    )

    await session.commit()
    balance_after = await _balance_for(session, saga.user_id)
    return _topup_response(saga, balance_after=balance_after)


@billing_router.post("/charges", response_model=ChargeResponse, status_code=status.HTTP_201_CREATED)
async def create_charge(
    body: ChargeCreateRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Response | ChargeResponse:
    """AC1 + AC2 lazy-seed + AC6 insufficient balance."""
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    cached_response = await _charge_replay_response_if_cached(
        session,
        body=body,
        user_id=user_id,
        idempotency_key=idempotency_key,
    )
    if cached_response is not None:
        return cached_response

    if not await _has_any_transactions(session, user_id):
        await _seed_demo_balance(session, user_id)

    balance_before = await _balance_for(session, user_id)
    if body.amount > balance_before:
        await session.commit()
        return _problem_response(
            title="Insufficient balance",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Required: ¥{body.amount}, available: ¥{balance_before}",
            errors=[
                ErrorDetail(
                    field_path="body.amount",
                    value=str(body.amount),
                    constraint="amount > balance",
                    remediation_hint_key="errors.422.insufficient_balance",
                )
            ],
        )

    # Story 5.A.5 — pre-charge guard (FR B6): require explicit confirm when warnings exist
    warnings = _classify_with_settings(body.amount, balance_before)
    if warnings and not body.confirmed:
        await session.commit()
        return _problem_response(
            title="Explicit Confirmation Required",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=warnings[0].message,
            errors=[
                ErrorDetail(
                    field_path="body.confirmed",
                    value="false",
                    constraint="warnings exist, confirmed must be true",
                    remediation_hint_key=warnings[0].remediation_hint_key,
                )
            ],
        )

    # 5.A.5 — audit trail: deterministic flag (boolean, not timestamp, so idempotent replays
    # produce the same body hash). The "when" is saga.created_at; the user_id is saga.user_id.
    include_confirmation_ref = bool(warnings and body.confirmed)

    orch = SagaOrchestrator(session)
    try:
        saga = await orch.start(
            saga_type=_charge_saga_type(body),
            user_id=user_id,
            idempotency_key=idempotency_key,
            payload=_charge_payload(body, include_confirmation_ref=include_confirmation_ref),
            amount=body.amount,
        )
    except CrossTenantKeyError as e:
        await session.rollback()
        return _problem_response(
            title="Cross-tenant key reuse forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except IdempotencyConflictError as e:
        await session.rollback()
        return _problem_response(
            title="Idempotency Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    balance_after = await _balance_for(session, user_id)
    response = ChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        amount=f"{body.amount:.2f}",
        currency="CNY",
        balance_before=f"{balance_before:.2f}",
        balance_after=f"{balance_after:.2f}",  # unchanged until /confirm
    )
    await _persist_charge_response_body(session, idempotency_key, response)
    await session.commit()
    return response


@billing_router.post(
    "/charges/{charge_id}/reserve",
    response_model=ReserveChargeResponse,
)
async def reserve_charge(
    charge_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> Response | ReserveChargeResponse:
    """Story 5.A.4 — split-phase reserve only (PENDING → RESERVED)."""
    orch = SagaOrchestrator(session)
    try:
        saga = await orch.get(charge_id)
    except SagaNotFoundError as e:
        await session.rollback()
        return _problem_response(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if saga.user_id != user_id:
        await session.rollback()
        return _problem_response(
            title="Forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="charge belongs to another user",
        )

    try:
        saga = await orch.apply(charge_id, "reserve")
    except (InvalidSagaTransitionError, SagaTerminalError) as e:
        await session.rollback()
        return _problem_response(
            title="Reserve Not Applicable",
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    await session.commit()
    balance_after = await _balance_for(session, user_id)

    return ReserveChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        amount_reserved=f"{saga.amount:.2f}" if saga.amount else "0.00",
        balance_after_reserve=f"{balance_after:.2f}",
    )


async def _ledger_rows_for_saga(
    session: AsyncSession, saga_id: uuid.UUID
) -> list[CreditTransaction]:
    """Read all credit_transactions rows tied to one saga (R1.3 rebuild)."""
    stmt = select(CreditTransaction).where(CreditTransaction.saga_id == saga_id)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


def _max_solve_seconds_from(saga: SagaInstance) -> float:
    """Return finalization cap seconds.

    Legacy 5.A.4 rows may still contain `payload_ref.max_solve_seconds`. New
    5.A.0 rows keep payload_ref pointer-only, so derive cap from reserved amount
    and configured LP rate.
    """
    raw = saga.payload_ref.get("max_solve_seconds") if saga.payload_ref else None
    if raw is None:
        if saga.amount is not None and settings.lp_rate_per_second > 0:
            return float(saga.amount / settings.lp_rate_per_second)
        return settings.charge_max_solve_seconds_default
    return float(raw)


def _discount_context(discount_multiplier: Decimal) -> dict[str, str]:
    if discount_multiplier == Decimal("1.0"):
        return {}
    return {"discount_multiplier": f"{discount_multiplier:.4f}"}


async def _billing_cost_attribution_exists(session: AsyncSession, charge_id: uuid.UUID) -> bool:
    stmt = (
        select(func.count())
        .select_from(CostAttribution)
        .where(
            CostAttribution.source_id == charge_id,
            CostAttribution.service == "billing-service",
            CostAttribution.cost_unit == CostUnit.SOLVER_SECOND.value,
        )
    )
    return bool((await session.execute(stmt)).scalar_one())


async def _record_billing_cost_attribution(
    session: AsyncSession,
    saga: SagaInstance,
    *,
    elapsed_seconds: float,
    finalize_status: str,
) -> None:
    """Best-effort Billing Saga cost hook; never blocks finalization."""
    try:
        async with session.begin_nested():
            if await _billing_cost_attribution_exists(session, saga.id):
                return

            metadata: dict[str, str] = {
                "saga_type": saga.saga_type,
                "charge_state": saga.current_state,
                "finalize_status": finalize_status,
            }
            purpose = saga.payload_ref.get("purpose") if saga.payload_ref else None
            if isinstance(purpose, str):
                metadata["purpose"] = purpose

            await record_cost_event(
                session,
                CostAttribution,
                CostTelemetryEvent(
                    tenant_id=saga.user_id,
                    service="billing-service",
                    cost_unit=CostUnit.SOLVER_SECOND,
                    value=Decimal(str(elapsed_seconds)),
                    source_id=saga.id,
                    metadata=metadata,
                ),
            )
    except Exception:
        logger.warning(
            "billing.cost_attribution.record_failed",
            extra={"charge_id": str(saga.id), "saga_type": saga.saga_type},
            exc_info=True,
        )


def _rebuild_finalize_response(
    saga: SagaInstance,
    ledger_rows: list[CreditTransaction],
    balance_after: Decimal,
) -> FinalizeChargeResponse:
    """R1.3 — replay/idempotent rebuild from terminal-state ledger rows.

    Ledger sign convention:
      kind=charge          → -reserved (debit, written by orchestrator service_success)
      kind=refund_partial  → +(reserved - actual)
      kind=refund          → +reserved (written by orchestrator user_cancel)
      kind=refund_reversal → -reserved (R1.1 net-zero compensation)

    For a successful charge: net = (-reserved) + (reserved - actual) = -actual.
    For a failure:           net = (+reserved) + (-reserved) = 0.
    """
    reserved = saga.amount or Decimal("0")
    charge_sum = sum(
        (r.amount for r in ledger_rows if r.kind == "charge"),
        start=Decimal("0"),
    )
    refund_partial = sum(
        (r.amount for r in ledger_rows if r.kind == "refund_partial"),
        start=Decimal("0"),
    )
    # actual_amount is what the user effectively paid (positive number)
    actual = -(charge_sum + refund_partial) if charge_sum < 0 else Decimal("0")
    # balance_before = balance_after - net_change; net_change for success = -actual
    balance_before = balance_after + actual
    return FinalizeChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        reserved_amount=f"{reserved:.2f}",
        actual_amount=f"{actual:.2f}",
        refund_partial_amount=f"{refund_partial:.2f}",
        balance_before=f"{balance_before:.2f}",
        balance_after=f"{balance_after:.2f}",
    )


def _refund_partial_total(ledger_rows: list[CreditTransaction]) -> Decimal:
    return sum(
        (row.amount for row in ledger_rows if row.kind == "refund_partial"),
        start=Decimal("0"),
    )


def _charged_actual_paid(ledger_rows: list[CreditTransaction]) -> Decimal:
    """Return positive amount paid after existing charge/refund_partial rows."""
    charge_sum = sum(
        (row.amount for row in ledger_rows if row.kind == "charge"),
        start=Decimal("0"),
    )
    refund_partial = _refund_partial_total(ledger_rows)
    if charge_sum >= 0:
        return Decimal("0")
    return -(charge_sum + refund_partial)


def _rebuild_auto_refund_response(
    saga: SagaInstance,
    ledger_rows: list[CreditTransaction],
    balance_after: Decimal,
) -> AutoRefundResponse:
    reserved = saga.amount or Decimal("0")
    mode: Literal["reserved_net_zero", "charged_rollback"] = (
        "reserved_net_zero" if saga.current_state == "refunded" else "charged_rollback"
    )
    refunded = Decimal("0")
    if mode == "charged_rollback":
        refunded = _charged_actual_paid(ledger_rows)
    balance_before = balance_after - refunded
    return AutoRefundResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        refund_mode=mode,
        reserved_amount=f"{reserved:.2f}",
        refunded_amount=f"{refunded:.2f}",
        balance_before=f"{balance_before:.2f}",
        balance_after=f"{balance_after:.2f}",
    )


def _auto_refund_context(
    body: AutoRefundRequest,
    *,
    refunded_amount: Decimal,
    reversed_partial_amount: Decimal | None = None,
) -> dict[str, str | float]:
    context: dict[str, str | float] = {
        "reason": body.reason,
        "source": body.source,
        "source_ref": body.source_ref,
        "refunded_amount": f"{refunded_amount:.4f}",
        "automatic_refund": "true",
    }
    if body.elapsed_seconds is not None:
        context["elapsed_seconds"] = body.elapsed_seconds
    if reversed_partial_amount is not None and reversed_partial_amount != Decimal("0"):
        context["reversed_partial_amount"] = f"{reversed_partial_amount:.4f}"
    return context


def _write_refund_auto_outbox(
    session: AsyncSession,
    saga: SagaInstance,
    *,
    from_state: str,
    body: AutoRefundRequest,
    refunded_amount: Decimal,
) -> None:
    payload: dict[str, str | float] = {
        "saga_id": str(saga.id),
        "charge_id": str(saga.id),
        "saga_type": saga.saga_type,
        "from_state": from_state,
        "to_state": saga.current_state,
        "reason": body.reason,
        "source": body.source,
        "source_ref": body.source_ref,
        "refunded_amount": f"{refunded_amount:.4f}",
    }
    if body.elapsed_seconds is not None:
        payload["elapsed_seconds"] = body.elapsed_seconds
    session.add(
        OutboxEvent(
            aggregate_type="saga_instance",
            aggregate_id=saga.id,
            event_type="billing.refund_auto.detected",
            event_version=1,
            payload=payload,
            headers={"compensation": "refund_auto"},
            occurred_at=datetime.now(UTC),
        )
    )


@billing_router.post(
    "/charges/{charge_id}/refund-auto",
    response_model=AutoRefundResponse,
)
async def refund_auto_charge(
    charge_id: uuid.UUID,
    body: AutoRefundRequest,
    _internal: None = Depends(require_internal_service),
    session: AsyncSession = Depends(get_session),
) -> Response | AutoRefundResponse:
    """Story 5.C.1 — trusted automatic refund for failed/cancelled/infeasible tasks."""
    orch = SagaOrchestrator(session)
    try:
        saga = await orch.get(charge_id)
    except SagaNotFoundError as e:
        await session.rollback()
        return _problem_response(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if not saga.saga_type.endswith("_charge"):
        await session.rollback()
        return _problem_response(
            title="Refund Not Applicable",
            status_code=status.HTTP_409_CONFLICT,
            detail="automatic refunds apply only to charge sagas",
        )

    if saga.current_state in ("refunded", "rolled_back"):
        ledger_rows = await _ledger_rows_for_saga(session, saga.id)
        balance_after = await _balance_for(session, saga.user_id)
        return _rebuild_auto_refund_response(saga, ledger_rows, balance_after)

    if saga.current_state in ("pending", "failed", "completed"):
        current_state = saga.current_state
        await session.rollback()
        return _problem_response(
            title="Refund Not Applicable",
            status_code=status.HTTP_409_CONFLICT,
            detail=f"automatic refund is not applicable from state {current_state!r}",
        )

    reserved_amount = saga.amount or Decimal("0")
    balance_before = await _balance_for(session, saga.user_id)
    from_state = saga.current_state

    if saga.current_state == "reserved":
        refunded_amount = Decimal("0")
        try:
            saga = await orch.apply(
                charge_id,
                "user_cancel",
                context={
                    "reserved_amount": f"{reserved_amount:.4f}",
                    **_auto_refund_context(body, refunded_amount=refunded_amount),
                },
            )
        except (InvalidSagaTransitionError, SagaTerminalError) as e:
            await session.rollback()
            return _problem_response(
                title="Refund Not Applicable",
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )

        session.add(
            CreditTransaction(
                user_id=saga.user_id,
                saga_id=saga.id,
                amount=-reserved_amount,
                kind="refund_reversal",
                currency="CNY",
                metadata_json={
                    "reason": "reservation never debited; automatic refund net-zero",
                    "auto_refund_reason": body.reason,
                    "source": body.source,
                    "source_ref": body.source_ref,
                },
                created_at=datetime.now(UTC),
            )
        )
        _write_refund_auto_outbox(
            session,
            saga,
            from_state=from_state,
            body=body,
            refunded_amount=refunded_amount,
        )
        await session.commit()
        balance_after = await _balance_for(session, saga.user_id)
        return AutoRefundResponse(
            charge_id=str(saga.id),
            current_state=saga.current_state,
            refund_mode="reserved_net_zero",
            reserved_amount=f"{reserved_amount:.2f}",
            refunded_amount=f"{refunded_amount:.2f}",
            balance_before=f"{balance_before:.2f}",
            balance_after=f"{balance_after:.2f}",
        )

    if saga.current_state == "charged":
        ledger_rows = await _ledger_rows_for_saga(session, saga.id)
        refunded_amount = _charged_actual_paid(ledger_rows)
        refund_partial = _refund_partial_total(ledger_rows)
        try:
            saga = await orch.apply(
                charge_id,
                "downstream_reject_late",
                context={
                    "reserved_amount": f"{reserved_amount:.4f}",
                    **_auto_refund_context(
                        body,
                        refunded_amount=refunded_amount,
                        reversed_partial_amount=refund_partial,
                    ),
                },
            )
        except (InvalidSagaTransitionError, SagaTerminalError) as e:
            await session.rollback()
            return _problem_response(
                title="Refund Not Applicable",
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )

        if refund_partial != Decimal("0"):
            session.add(
                CreditTransaction(
                    user_id=saga.user_id,
                    saga_id=saga.id,
                    amount=-refund_partial,
                    kind="refund_reversal",
                    currency="CNY",
                    metadata_json={
                        "reason": "prior partial refund already returned; rollback refunds actual paid only",
                        "auto_refund_reason": body.reason,
                        "source": body.source,
                        "source_ref": body.source_ref,
                        "reversed_partial_amount": f"{refund_partial:.4f}",
                    },
                    created_at=datetime.now(UTC),
                )
            )
        _write_refund_auto_outbox(
            session,
            saga,
            from_state=from_state,
            body=body,
            refunded_amount=refunded_amount,
        )
        await session.commit()
        balance_after = await _balance_for(session, saga.user_id)
        return AutoRefundResponse(
            charge_id=str(saga.id),
            current_state=saga.current_state,
            refund_mode="charged_rollback",
            reserved_amount=f"{reserved_amount:.2f}",
            refunded_amount=f"{refunded_amount:.2f}",
            balance_before=f"{balance_before:.2f}",
            balance_after=f"{balance_after:.2f}",
        )

    current_state = saga.current_state
    await session.rollback()
    return _problem_response(
        title="Refund Not Applicable",
        status_code=status.HTTP_409_CONFLICT,
        detail=f"automatic refund is not applicable from state {current_state!r}",
    )


@billing_router.post(
    "/charges/{charge_id}/finalize",
    response_model=FinalizeChargeResponse,
)
async def finalize_charge(
    charge_id: uuid.UUID,
    body: FinalizeChargeRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> Response | FinalizeChargeResponse:
    """Story 5.A.4 — RESERVED → CHARGED (per-formula amount) or REFUNDED."""
    orch = SagaOrchestrator(session)
    try:
        saga = await orch.get(charge_id)
    except SagaNotFoundError as e:
        await session.rollback()
        return _problem_response(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if saga.user_id != user_id:
        await session.rollback()
        return _problem_response(
            title="Forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="charge belongs to another user",
        )

    # R1.3 — idempotent replay if already terminal
    if saga.current_state in ("charged", "completed", "refunded", "rolled_back"):
        ledger_rows = await _ledger_rows_for_saga(session, saga.id)
        balance_after = await _balance_for(session, user_id)
        return _rebuild_finalize_response(saga, ledger_rows, balance_after)

    reserved_amount = saga.amount or Decimal("0")
    balance_before = await _balance_for(session, user_id)

    if body.status == "success":
        max_seconds = _max_solve_seconds_from(saga)
        actual = compute_charge_amount(
            elapsed_seconds=body.elapsed_seconds,
            max_solve_seconds=max_seconds,
            rate_per_second=settings.lp_rate_per_second,
            min_amount=settings.charge_min_amount,
            reserved_amount=reserved_amount,
            discount_multiplier=body.discount_multiplier,
        )

        # Apply transition first — orchestrator writes the `-reserved kind=charge` row + outbox event
        try:
            saga = await orch.apply(
                charge_id,
                "service_success",
                context={
                    "reserved_amount": f"{reserved_amount:.4f}",
                    "actual_amount": f"{actual:.4f}",
                    "elapsed_seconds": body.elapsed_seconds,
                    **_discount_context(body.discount_multiplier),
                },
            )
        except (InvalidSagaTransitionError, SagaTerminalError) as e:
            await session.rollback()
            return _problem_response(
                title="Finalize Not Applicable",
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )

        # AC4 fix — orchestrator writes -reserved (i.e. saga.amount × -1) via service_success.
        # If actual < reserved, write a compensating +refund_partial row in same tx so the
        # ledger nets to -actual (the correct charge).
        refund_partial = Decimal("0")
        if actual < reserved_amount:
            refund_partial = reserved_amount - actual
            session.add(
                CreditTransaction(
                    user_id=user_id,
                    saga_id=saga.id,
                    amount=refund_partial,
                    kind="refund_partial",
                    currency="CNY",
                    metadata_json={
                        "reason": "elapsed < max_solve_seconds",
                        "elapsed_seconds": body.elapsed_seconds,
                        "actual_amount": f"{actual:.4f}",
                        **_discount_context(body.discount_multiplier),
                    },
                    created_at=datetime.now(UTC),
                )
            )

        await session.flush()
        await _record_billing_cost_attribution(
            session,
            saga,
            elapsed_seconds=body.elapsed_seconds,
            finalize_status=body.status,
        )
        await session.commit()
        balance_after = await _balance_for(session, user_id)
        return FinalizeChargeResponse(
            charge_id=str(saga.id),
            current_state=saga.current_state,
            reserved_amount=f"{reserved_amount:.2f}",
            actual_amount=f"{actual:.2f}",
            refund_partial_amount=f"{refund_partial:.2f}",
            balance_before=f"{balance_before:.2f}",
            balance_after=f"{balance_after:.2f}",
        )

    # status == "failure" — apply user_cancel; orchestrator writes +reserved kind=refund row.
    # R1.1: write compensating -reserved kind=refund_reversal row (net zero) since reserve
    # never wrote a debit. Both rows live in audit trail.
    try:
        saga = await orch.apply(
            charge_id,
            "user_cancel",
            context={
                "failure_reason": body.failure_reason or "unknown",
                "elapsed_seconds": body.elapsed_seconds,
            },
        )
    except (InvalidSagaTransitionError, SagaTerminalError) as e:
        await session.rollback()
        return _problem_response(
            title="Finalize Not Applicable",
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    session.add(
        CreditTransaction(
            user_id=user_id,
            saga_id=saga.id,
            amount=-reserved_amount,
            kind="refund_reversal",
            currency="CNY",
            metadata_json={
                "reason": "reservation never debited; net-zero compensation",
                "failure_reason": body.failure_reason or "unknown",
            },
            created_at=datetime.now(UTC),
        )
    )

    await session.commit()
    balance_after = await _balance_for(session, user_id)
    return FinalizeChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        reserved_amount=f"{reserved_amount:.2f}",
        actual_amount="0.00",
        refund_partial_amount="0.00",
        balance_before=f"{balance_before:.2f}",
        balance_after=f"{balance_after:.2f}",
    )


@billing_router.post(
    "/charges/{charge_id}/confirm",
    response_model=ChargeResponse,
    deprecated=True,
)
async def confirm_charge(
    charge_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> Response | ChargeResponse:
    """DEPRECATED (5.A.1) — apply reserve + service_success in one call.

    Replaced by the 2-phase /reserve + /finalize endpoints (Story 5.A.4).
    Slated for removal in M3.
    """
    orch = SagaOrchestrator(session)
    try:
        saga = await orch.get(charge_id)
    except SagaNotFoundError as e:
        await session.rollback()
        return _problem_response(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if saga.user_id != user_id:
        await session.rollback()
        return _problem_response(
            title="Forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="charge belongs to another user",
        )

    balance_before = await _balance_for(session, user_id)

    try:
        saga = await orch.apply(charge_id, "reserve")
        saga = await orch.apply(charge_id, "service_success")
    except (InvalidSagaTransitionError, SagaTerminalError) as e:
        await session.rollback()
        return _problem_response(
            title="Charge Already Finalized",
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    await session.commit()
    balance_after = await _balance_for(session, user_id)

    return ChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        amount=f"{saga.amount:.2f}" if saga.amount else "0.00",
        currency="CNY",
        balance_before=f"{balance_before:.2f}",
        balance_after=f"{balance_after:.2f}",
    )


__all__ = ["billing_router"]
