"""Pytest path bootstrap for solver-orchestrator tests."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

APP_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
ROOT_DIR = Path(__file__).resolve().parents[3]
PYTHON_SDK_SRC_DIR = ROOT_DIR / "packages" / "python-sdk" / "src"
SHARED_PKG_DIR = ROOT_DIR / "packages" / "shared-py"
for path in (APP_SRC_DIR, SHARED_PKG_DIR, PYTHON_SDK_SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
