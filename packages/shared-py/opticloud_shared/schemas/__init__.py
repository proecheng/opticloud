"""OptiCloud canonical Pydantic schemas — single source of truth for OpenAPI codegen.

Story 0.4 — Pydantic schemas → OpenAPI 3.0 → TypeScript types (single source).
P17 (shared-types) + P64 (OpenAPI Codegen + drift check).

Modules:
- errors: RFC 7807 + errors[] detail schema (FG1.3)
- common: shared types (Pagination, IDs)
"""

from opticloud_shared.schemas.common import (
    Cursor,
    IdempotencyKey,
    PaginatedResponse,
)
from opticloud_shared.schemas.errors import (
    ErrorDetail,
    ErrorResponse,
    Problem,
)

__all__ = [
    "Cursor",
    "ErrorDetail",
    "ErrorResponse",
    "IdempotencyKey",
    "PaginatedResponse",
    "Problem",
]
