"""Schemathesis fixtures + helpers for OpenAPI contract property tests.

Story 0.5b foundation; full CI gate is Story M3.2 Contract Test framework.

Two load patterns:
1. From URL (running service)        — schemathesis_from_url("http://localhost:8001")
2. From static spec file (CI offline) — schemathesis_from_path("openapi.json")

The latter is preferred for CI (no service start required, deterministic).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import schemathesis


def schemathesis_from_url(
    base_url: str, *, openapi_path: str = "/openapi.json"
) -> schemathesis.BaseSchema:
    """Load OpenAPI schema from a running service.

    Args:
        base_url: e.g. "http://localhost:8001"
        openapi_path: path component returning OpenAPI JSON (default Story 0.6 spec)

    Returns:
        Schemathesis schema usable with @schema.parametrize().

    Notes:
        Requires the service to be running. Prefer schemathesis_from_path() for CI.
    """
    import schemathesis

    return schemathesis.openapi.from_url(f"{base_url.rstrip('/')}{openapi_path}")


def schemathesis_from_path(spec_path: str | Path) -> schemathesis.BaseSchema:
    """Load OpenAPI schema from a static file (CI-friendly, no running service).

    Args:
        spec_path: absolute or repo-relative path to openapi.json / openapi.yaml

    Returns:
        Schemathesis schema usable with @schema.parametrize().
    """
    import schemathesis

    path = Path(spec_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return schemathesis.openapi.from_path(path)
