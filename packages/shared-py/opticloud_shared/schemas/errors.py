"""RFC 7807 + errors[] detail schema (FG1.3 Critical, PRD v1.1).

Single source of truth for error response shape across all services + SDKs.

Architecture references:
- PRD v1.1 §Error Codes RFC 7807 + errors[] detail schema
- FG1.3: errors[] with field_path / value / constraint / remediation_hint_key
- O7: 4xx/402/429/422 必带 next_action_url + errors[]
- i18n 单源: detail/title/remediation_hint_key 必须来自 packages/i18n/errors.<lang>.yaml
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """RFC 7807 errors[] detail object — FG1.3 Critical.

    Each detail describes one specific validation violation.
    SDKs (Python/Node/Go) preserve this structure for `error.locate()` helper.
    """

    field_path: str = Field(
        ...,
        description=(
            "Dot/bracket notation locating violating field "
            "(e.g. 'st.A[2][1]' or 'options.max_solve_seconds')"
        ),
        examples=["st.b[0]", "options.max_solve_seconds"],
    )
    value: Any = Field(
        default=None,
        description="Actual value provided (may be redacted for sensitive fields)",
    )
    constraint: str = Field(
        ...,
        description="Specific constraint violated (machine-parseable; SDK uses for client hints)",
        examples=["must be > 0", "infeasible_lp"],
    )
    remediation_hint_key: str = Field(
        ...,
        description=(
            "i18n key pointing to packages/i18n/errors.<lang>.yaml entry "
            "(format: errors.<status>.<rule>)"
        ),
        examples=["errors.422.infeasible", "errors.402.topup"],
    )


class Problem(BaseModel):
    """RFC 7807 Problem Details — base error response shape."""

    type: str = Field(
        default="about:blank",
        description="URI identifying problem type (e.g. https://api.opticloud.cn/errors/insufficient_credits)",
    )
    title: str = Field(
        ...,
        description="Short human-readable summary (i18n via Accept-Language)",
        examples=["Insufficient Credits", "Validation Error"],
    )
    status: int = Field(
        ...,
        description="HTTP status code mirroring response status",
        examples=[400, 402, 422],
    )
    detail: str = Field(
        ...,
        description=(
            "Human-readable explanation (i18n via Accept-Language; "
            "must come from packages/i18n/errors.<lang>.yaml — enforced by ESLint)"
        ),
    )
    instance: str | None = Field(
        default=None,
        description="URI of the specific occurrence (e.g. /v1/optimizations)",
    )
    request_id: str | None = Field(default=None, description="Correlation ID")
    trace_id: str | None = Field(default=None, description="OpenTelemetry trace ID")


class ErrorResponse(Problem):
    """OptiCloud full error response — extends RFC 7807 Problem.

    FG1.3 Critical M1: 4xx/422 必带 errors[] (≥1 detail object) + next_action_url.
    """

    errors: list[ErrorDetail] = Field(
        default_factory=list,
        description=(
            "Detail objects (FG1.3). For 4xx/422 errors MUST include ≥1 detail. "
            "SDKs preserve original structure via error.errors field."
        ),
    )
    next_action_url: str | None = Field(
        default=None,
        description=(
            "Actionable URL for user remediation (FR O7 + FG1.3). "
            "Required for 4xx/402/429 responses."
        ),
        examples=["https://console.opticloud.cn/topup?suggested_amount=10"],
    )
