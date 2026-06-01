"""Check OpenAPI spec drift between checked-in files and generated-from-code.

Story 0.4 + P64 OpenAPI Codegen + drift check.

Usage:
    uv run python scripts/check_openapi_drift.py

Exit codes:
    0: no drift
    1: drift detected (must regenerate + commit)
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENAPI_DIR = REPO_ROOT / "packages" / "shared-ts" / "openapi"


def main() -> int:
    if not OPENAPI_DIR.exists():
        print("  WARN No openapi/ directory; run `generate_openapi.py` first.")
        return 1

    # Generate fresh spec into temp dir
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        env = {"OPENAPI_OUTPUT_DIR": str(tmp_dir)}
        result = subprocess.run(
            ["uv", "run", "python", "scripts/generate_openapi.py"],
            cwd=REPO_ROOT,
            env={**dict(os.environ), **env},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            print(f"  ERROR Generate failed: {result.stderr}")
            return 1

        generated = {path.name: path.read_text(encoding="utf-8") for path in tmp_dir.glob("*.json")}
        checked_in = {
            path.name: path.read_text(encoding="utf-8") for path in OPENAPI_DIR.glob("*.json")
        }
        if generated != checked_in:
            print("  ERROR OpenAPI spec drift detected!")
            print("     The checked-in openapi/ files differ from generated.")
            print("     Run `uv run python scripts/generate_openapi.py` + commit.")
            missing = sorted(generated.keys() - checked_in.keys())
            stale = sorted(checked_in.keys() - generated.keys())
            changed = sorted(
                name
                for name in generated.keys() & checked_in.keys()
                if generated[name] != checked_in[name]
            )
            if missing:
                print(f"     Missing checked-in files: {', '.join(missing)}")
            if stale:
                print(f"     Stale checked-in files: {', '.join(stale)}")
            if changed:
                print(f"     Changed files: {', '.join(changed)}")
            return 1

    print("  OK No OpenAPI drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
