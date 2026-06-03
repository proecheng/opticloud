"""Pytest path bootstrap for solver-orchestrator tests."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

APP_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
ROOT_DIR = Path(__file__).resolve().parents[3]
PYTHON_SDK_SRC_DIR = ROOT_DIR / "packages" / "python-sdk" / "src"
SHARED_PKG_DIR = ROOT_DIR / "packages" / "shared-py"
BILLING_SERVICE_SRC_DIR = ROOT_DIR / "apps" / "billing-service" / "src"
for path in (APP_SRC_DIR, SHARED_PKG_DIR, PYTHON_SDK_SRC_DIR, BILLING_SERVICE_SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(autouse=True)
def allow_rate_limit_by_default(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Most solver tests are not Redis integration tests; default them to allowed."""
    try:
        from solver_orchestrator import rate_limit
    except ImportError:
        yield
        return

    async def _allow(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(rate_limit, "enforce_rate_limit", _allow)
    yield
