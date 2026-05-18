"""Shared types: IDs, pagination, idempotency."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class IdempotencyKey(BaseModel):
    """P23 Idempotency-Key header (uuid v4)."""

    key: str = Field(..., description="UUID v4 idempotency key")


class Cursor(BaseModel):
    """P9 Cursor-based pagination."""

    cursor: str | None = Field(default=None, description="Opaque cursor for next page")
    limit: int = Field(default=50, ge=1, le=200)


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
