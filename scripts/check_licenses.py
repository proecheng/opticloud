#!/usr/bin/env python
"""OptiCloud license check (Story 0.5 + CRG9 fix).

This is a cross-platform placeholder so pre-commit can run on Windows and Linux
without relying on a shell interpreter. It mirrors the shell script's output.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.stdout.write("OptiCloud license check...\n")

    if (repo_root / "uv.lock").exists():
        sys.stdout.write("  Python (uv): scanning dependencies...\n")
        sys.stdout.write(
            "  WARNING: License scan logic pending implementation (Sprint 0 W2 task).\n"
        )

    if (repo_root / "pnpm-lock.yaml").exists():
        sys.stdout.write("  Node (pnpm): scanning dependencies...\n")
        sys.stdout.write(
            "  WARNING: License scan logic pending implementation (Sprint 0 W2 task).\n"
        )

    sys.stdout.write("OK: License check complete (placeholder pass).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
