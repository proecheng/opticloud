"""Check OpenAPI spec drift between checked-in files and generated-from-code.

Story 0.4 + P64 OpenAPI Codegen + drift check.

Usage:
    uv run python scripts/check_openapi_drift.py

Exit codes:
    0: no drift
    1: drift detected (must regenerate + commit)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENAPI_DIR = REPO_ROOT / "packages" / "shared-ts" / "openapi"


def main() -> int:
    if not OPENAPI_DIR.exists():
        print("  ⚠️  No openapi/ directory; run `generate_openapi.py` first.")
        return 1

    # Generate fresh spec into temp dir
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        env_override = {"OPENAPI_OUTPUT_DIR": str(tmp_dir)}

        # For now, simply regenerate to actual output and diff via git
        # (Production version would generate to temp + diff)
        result = subprocess.run(
            ["uv", "run", "python", "scripts/generate_openapi.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"  ❌ Generate failed: {result.stderr}")
            return 1

        # Check git status for changes in openapi/
        git_diff = subprocess.run(
            ["git", "diff", "--exit-code", "--", str(OPENAPI_DIR)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if git_diff.returncode != 0:
            print("  ❌ OpenAPI spec drift detected!")
            print("     The checked-in openapi/ files differ from generated.")
            print("     Run `uv run python scripts/generate_openapi.py` + commit.")
            print()
            print("Diff:")
            print(git_diff.stdout)
            return 1

    print("  ✅ No OpenAPI drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
