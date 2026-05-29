from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from chat_service import __version__
from chat_service.coder import generate_code_with_llm
from chat_service.confidence_display import generate_confidence_display_preview
from chat_service.config import load_internal_beta_config
from chat_service.critic import generate_critic_validation_with_llm
from chat_service.formulator import extract_formulation_with_llm
from chat_service.gate import InternalBetaAccessDeniedError, validate_internal_beta_access
from chat_service.human_review import generate_human_review_preview
from chat_service.language_response import generate_language_response_with_llm
from chat_service.llm_intent import route_intent_with_llm
from chat_service.model_preview import generate_model_preview
from chat_service.router_preview import build_message_excerpt, detect_locale
from chat_service.sandbox import generate_sandbox_preview
from chat_service.schemas import (
    AigcGate,
    ChatInternalBetaMessageRequest,
    ChatInternalBetaMessageResponse,
)
from chat_service.streaming import build_stream_events, iter_sse_payload

app = FastAPI(
    title="OptiCloud Chat Service",
    version=__version__,
    description="Story 4.A.1 — internal beta NL input receiving gate.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "chat-service"}


@app.post(
    "/v1/chat/internal-beta/messages",
    response_model=ChatInternalBetaMessageResponse,
)
async def create_internal_beta_message(
    raw_request: Request,
    x_internal_beta_tenant: Annotated[str | None, Header(alias="X-Internal-Beta-Tenant")] = None,
    x_internal_beta_user: Annotated[str | None, Header(alias="X-Internal-Beta-User")] = None,
    x_internal_beta_token: Annotated[str | None, Header(alias="X-Internal-Beta-Token")] = None,
) -> ChatInternalBetaMessageResponse:
    request = await _validate_internal_beta_request(
        raw_request,
        x_internal_beta_tenant=x_internal_beta_tenant,
        x_internal_beta_user=x_internal_beta_user,
        x_internal_beta_token=x_internal_beta_token,
    )
    return _build_internal_beta_response(
        request,
        tenant=x_internal_beta_tenant or "",
        user=x_internal_beta_user or "",
    )


@app.post("/v1/chat/internal-beta/messages/stream")
async def stream_internal_beta_message(
    raw_request: Request,
    x_internal_beta_tenant: Annotated[str | None, Header(alias="X-Internal-Beta-Tenant")] = None,
    x_internal_beta_user: Annotated[str | None, Header(alias="X-Internal-Beta-User")] = None,
    x_internal_beta_token: Annotated[str | None, Header(alias="X-Internal-Beta-Token")] = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    request = await _validate_internal_beta_request(
        raw_request,
        x_internal_beta_tenant=x_internal_beta_tenant,
        x_internal_beta_user=x_internal_beta_user,
        x_internal_beta_token=x_internal_beta_token,
    )
    response = _build_internal_beta_response(
        request,
        tenant=x_internal_beta_tenant or "",
        user=x_internal_beta_user or "",
    )
    events = build_stream_events(
        message_id=response.message_id,
        locale=response.locale,
        content=response.language_preview.summary,
        model_preview_id=response.model_preview.preview_id,
        model_preview_status=response.model_preview.status,
        aigc_watermark_trace_id=response.language_preview.aigc_watermark.trace_id,
        aigc_gate=response.aigc_gate.model_dump(mode="json"),
    )
    return StreamingResponse(
        iter_sse_payload(events, last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _validate_internal_beta_request(
    raw_request: Request,
    *,
    x_internal_beta_tenant: str | None,
    x_internal_beta_user: str | None,
    x_internal_beta_token: str | None,
) -> ChatInternalBetaMessageRequest:
    config = load_internal_beta_config()
    try:
        validate_internal_beta_access(
            config,
            tenant=x_internal_beta_tenant,
            user=x_internal_beta_user,
            token=x_internal_beta_token,
        )
    except InternalBetaAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    try:
        request = ChatInternalBetaMessageRequest.model_validate(await raw_request.json())
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid JSON body") from exc
    return request


def _build_internal_beta_response(
    request: ChatInternalBetaMessageRequest,
    *,
    tenant: str,
    user: str,
) -> ChatInternalBetaMessageResponse:
    locale = request.locale or detect_locale(request.message)
    message_excerpt = build_message_excerpt(request.message)
    message_id = _message_id(
        tenant=tenant,
        user=user,
        message=request.message,
        client_request_id=request.client_request_id,
    )
    intent_result = route_intent_with_llm(
        message=request.message,
        locale=locale,
        prompt_id=message_id,
    )
    formulator_result = extract_formulation_with_llm(
        message=request.message,
        locale=locale,
        prompt_id=message_id,
        router_preview=intent_result.preview,
    )
    coder_result = generate_code_with_llm(
        message=request.message,
        locale=locale,
        prompt_id=message_id,
        formulator_preview=formulator_result.preview,
    )
    critic_result = generate_critic_validation_with_llm(
        locale=locale,
        prompt_id=message_id,
        coder_preview=coder_result.preview,
    )
    human_review_result = generate_human_review_preview(
        message_id=message_id,
        critic_preview=critic_result.preview,
    )
    confidence_display_result = generate_confidence_display_preview(
        critic_preview=critic_result.preview,
        human_review_escalated=human_review_result.preview.escalated,
    )
    sandbox_result = generate_sandbox_preview(
        coder_preview=coder_result.preview,
        critic_preview=critic_result.preview,
    )
    model_preview = generate_model_preview(
        prompt_id=message_id,
        formulator_preview=formulator_result.preview,
        coder_preview=coder_result.preview,
        critic_preview=critic_result.preview,
        sandbox_preview=sandbox_result.preview,
        human_review=human_review_result.preview,
        sandbox_invoked=sandbox_result.sandbox_invoked,
    )
    language_result = generate_language_response_with_llm(
        message=request.message,
        locale=locale,
        prompt_id=message_id,
        message_excerpt=message_excerpt,
        router_preview=intent_result.preview,
        formulator_preview=formulator_result.preview,
        coder_preview=coder_result.preview,
    )

    return ChatInternalBetaMessageResponse(
        mode="internal_beta",
        public_access=False,
        message_id=message_id,
        message_excerpt=message_excerpt,
        locale=locale,
        router_preview=intent_result.preview,
        formulator_preview=formulator_result.preview,
        coder_preview=coder_result.preview,
        critic_preview=critic_result.preview,
        sandbox_preview=sandbox_result.preview,
        human_review=human_review_result.preview,
        critic_confidence_display=confidence_display_result.preview,
        model_preview=model_preview,
        language_preview=language_result.preview,
        aigc_gate=AigcGate(status="filing_pending", public_surface="hidden"),
        llm_invoked=(
            intent_result.llm_invoked
            or formulator_result.formulator_invoked
            or coder_result.coder_invoked
            or critic_result.critic_llm_invoked
            or language_result.language_invoked
        ),
        critic_invoked=critic_result.critic_invoked,
        critic_llm_invoked=critic_result.critic_llm_invoked,
        provider_request_sent=(
            intent_result.provider_request_sent
            or formulator_result.provider_request_sent
            or coder_result.provider_request_sent
            or critic_result.provider_request_sent
            or language_result.provider_request_sent
        ),
        solver_invoked=False,
        sandbox_invoked=sandbox_result.sandbox_invoked,
    )


def _message_id(
    *,
    tenant: str,
    user: str,
    message: str,
    client_request_id: str | None,
) -> str:
    digest = hashlib.sha256(
        "\n".join([tenant, user, client_request_id or "", message]).encode("utf-8")
    ).hexdigest()
    return f"msg_{digest[:24]}"
