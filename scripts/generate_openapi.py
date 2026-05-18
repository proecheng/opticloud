"""Generate OpenAPI 3.0 spec from FastAPI apps + canonical Pydantic schemas.

Story 0.4 — Pydantic → OpenAPI → TS types pipeline.

Usage:
    uv run python scripts/generate_openapi.py

Outputs:
    packages/shared-ts/openapi/auth-service.json
    packages/shared-ts/openapi/<service>.json (other services as they come online)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "packages" / "shared-ts" / "openapi"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_auth_service() -> Path:
    """Generate openapi.json from auth-service FastAPI app."""
    sys.path.insert(0, str(REPO_ROOT / "apps" / "auth-service" / "src"))
    sys.path.insert(0, str(REPO_ROOT / "packages" / "shared-py"))

    from auth_service.main import app  # type: ignore[import-not-found]

    spec = app.openapi()
    output = OUTPUT_DIR / "auth-service.json"
    output.write_text(json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False))
    print(f"  ✅ {output.relative_to(REPO_ROOT)} ({len(spec.get('paths', {}))} paths)")
    return output


def main() -> int:
    print("OptiCloud OpenAPI generation...")
    try:
        generate_auth_service()
    except ImportError as e:
        print(f"  ⚠️  auth-service import failed: {e}")
        print("     Run `uv sync` first to install deps.")
        return 1

    # Future: solver-orchestrator, billing-service, capability-registry, etc.
    print("✅ OpenAPI generation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
