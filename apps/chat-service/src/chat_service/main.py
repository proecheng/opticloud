from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from chat_service import __version__
from chat_service.config import load_internal_beta_config
from chat_service.formulator import extract_formulation_with_llm
from chat_service.gate import InternalBetaAccessDeniedError, validate_internal_beta_access
from chat_service.llm_intent import route_intent_with_llm
from chat_service.router_preview import build_message_excerpt, detect_locale
from chat_service.schemas import (
    AigcGate,
    ChatInternalBetaMessageRequest,
    ChatInternalBetaMessageResponse,
)

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

    locale = request.locale or detect_locale(request.message)
    message_id = _message_id(
        tenant=x_internal_beta_tenant or "",
        user=x_internal_beta_user or "",
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

    return ChatInternalBetaMessageResponse(
        mode="internal_beta",
        public_access=False,
        message_id=message_id,
        message_excerpt=build_message_excerpt(request.message),
        locale=locale,
        router_preview=intent_result.preview,
        formulator_preview=formulator_result.preview,
        aigc_gate=AigcGate(status="filing_pending", public_surface="hidden"),
        llm_invoked=intent_result.llm_invoked or formulator_result.formulator_invoked,
        provider_request_sent=intent_result.provider_request_sent,
        solver_invoked=False,
        sandbox_invoked=False,
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
