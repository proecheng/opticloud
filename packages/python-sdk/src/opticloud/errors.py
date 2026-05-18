"""OptiCloud SDK error types — FG1.3 SDK contract.

The SDK preserves the full errors[] structure from RFC 7807 responses
and exposes a `error.locate(field_path)` helper for client-side inspection.

Three-language SDK consistency (A-S3 fix):
- Python: e.locate("st.A[2][1]") -> value (this file)
- Node:   e.locate("st.A[2][1]") -> value (packages/node-sdk, future)
- Go:     err.Locate("st.A[2][1]") -> value (packages/go-sdk, future)
"""

from __future__ import annotations

import re
from typing import Any


class OptiCloudError(Exception):
    """Base SDK exception."""


class OptiCloudHTTPError(OptiCloudError):
    """HTTP error response from OptiCloud API (RFC 7807 + errors[] preserved).

    Attributes:
        status: HTTP status code
        type: RFC 7807 type URI
        title: human-readable title (i18n)
        detail: human-readable detail (i18n)
        errors: list of error detail dicts (FG1.3 SDK contract)
        next_action_url: actionable URL for user
        request_id, trace_id: correlation IDs
        raw: full original response dict
    """

    def __init__(
        self,
        status: int,
        type: str = "about:blank",
        title: str = "",
        detail: str = "",
        instance: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        next_action_url: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.type = type
        self.title = title
        self.detail = detail
        self.instance = instance
        self.errors: list[dict[str, Any]] = errors or []
        self.next_action_url = next_action_url
        self.request_id = request_id
        self.trace_id = trace_id
        self.raw = raw or {}
        super().__init__(f"[{status}] {title}: {detail}")

    # ===== FG1.3 + L1: error.locate() helper =====

    def locate(self, field_path: str) -> Any:
        """Return the `value` field of the first error detail matching `field_path`.

        Example:
            try:
                client.optimize(...)
            except OptiCloudHTTPError as e:
                bad_value = e.locate("st.A[2][1]")
                # bad_value is whatever the server flagged as violating

        Args:
            field_path: Dot/bracket notation (e.g. "st.A[2][1]", "options.max_solve_seconds")

        Returns:
            The value field from the matching ErrorDetail, or None if no match.
        """
        for detail in self.errors:
            if detail.get("field_path") == field_path:
                return detail.get("value")
        return None

    def locate_all(self, field_path: str) -> list[Any]:
        """Return all values for a field_path (in case multiple errors).

        Useful when one field has multiple violations (rare but possible).
        """
        return [d.get("value") for d in self.errors if d.get("field_path") == field_path]

    def find_constraint(self, constraint_pattern: str) -> list[dict[str, Any]]:
        """Find all error details where constraint matches regex pattern.

        Example:
            e.find_constraint(r"infeasible") -> [{field_path: "st", ...}]
        """
        pat = re.compile(constraint_pattern)
        return [d for d in self.errors if pat.search(d.get("constraint", ""))]

    def remediation_keys(self) -> list[str]:
        """Return all i18n remediation_hint_key values (FG1.3)."""
        return [
            d.get("remediation_hint_key", "") for d in self.errors if d.get("remediation_hint_key")
        ]

    @classmethod
    def from_response(cls, status: int, body: dict[str, Any]) -> OptiCloudHTTPError:
        """Construct from raw RFC 7807 response body."""
        return cls(
            status=status,
            type=body.get("type", "about:blank"),
            title=body.get("title", ""),
            detail=body.get("detail", ""),
            instance=body.get("instance"),
            errors=body.get("errors", []),
            next_action_url=body.get("next_action_url"),
            request_id=body.get("request_id"),
            trace_id=body.get("trace_id"),
            raw=body,
        )
