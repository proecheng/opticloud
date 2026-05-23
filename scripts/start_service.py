"""Start an OptiCloud Python service with explicit source-path wiring.

This launcher avoids relying on editable-install .pth resolution, which has
been flaky on Windows in this workspace path. It is used by Playwright's
local webServer hooks for cross-platform service startup.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "service",
        choices=("auth-service", "solver-orchestrator"),
        help="Service name to start.",
    )
    parser.add_argument(
        "port",
        type=int,
        help="TCP port to bind.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (default: 127.0.0.1).",
    )
    return parser


def add_source_paths(repo_root: Path, service: str) -> None:
    paths = [
        repo_root / "packages" / "shared-py",
        repo_root / "packages" / "python-sdk" / "src",
    ]
    if service == "auth-service":
        paths.append(repo_root / "apps" / "auth-service" / "src")
    elif service == "solver-orchestrator":
        paths.append(repo_root / "apps" / "solver-orchestrator" / "src")
    else:  # pragma: no cover - argparse already constrains this.
        raise ValueError(f"unsupported service: {service}")

    sys.path[:0] = [str(path) for path in paths]


def main() -> None:
    args = build_parser().parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    add_source_paths(repo_root, args.service)

    if args.service == "auth-service":
        app = "auth_service.main:app"
    else:
        app = "solver_orchestrator.main:app"

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
