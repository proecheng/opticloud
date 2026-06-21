"""Validate staging deployment verification documentation and static deploy gates.

This validator is intentionally static. It confirms that the repository contains
a repeatable staging verification path without claiming live production proof.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "staging-deployment-verification.md"
README_PATH = REPO_ROOT / "README.md"
BLUE_GREEN_VALIDATOR = REPO_ROOT / "scripts" / "validate_blue_green_deploy.py"
K8S_VALIDATOR = REPO_ROOT / "scripts" / "validate_k8s_network_policies.py"
BLUE_COMPOSE = REPO_ROOT / "docker-compose.blue.yml"
GREEN_COMPOSE = REPO_ROOT / "docker-compose.green.yml"
LOCAL_COMPOSE = REPO_ROOT / "docker-compose.yml"
K8S_DIR = REPO_ROOT / "infra" / "k8s" / "production"

REQUIRED_FILES = (
    RUNBOOK_PATH,
    README_PATH,
    BLUE_GREEN_VALIDATOR,
    K8S_VALIDATOR,
    BLUE_COMPOSE,
    GREEN_COMPOSE,
    LOCAL_COMPOSE,
    K8S_DIR / "namespaces.yaml",
    K8S_DIR / "networkpolicies.yaml",
)

RUNBOOK_REQUIRED_PHRASES = (
    "staging verification readiness",
    "does not claim that production is deployed",
    "Local dependency smoke",
    "Blue/green static verification",
    "Kubernetes manifest static verification",
    "Optional live staging smoke",
    "OPTICLOUD_STAGING_WEB_URL",
    "OPTICLOUD_STAGING_AUTH_URL",
    "OPTICLOUD_STAGING_SOLVER_URL",
    "Do not commit staging URLs",
    "Do not call static validation \"production verified\"",
    "BLUE_GREEN_SWITCH_CMD",
)

README_REQUIRED_PHRASES = (
    "docs/runbooks/staging-deployment-verification.md",
    "Live staging smoke",
    "staging verification",
)

FORBIDDEN_RUNBOOK_PHRASES = (
    "status: production verified",
    "production verified: true",
    "生产已验证：是",
    "ack enforcement verified: true",
    "blue/green switch success: true",
)


def validate_required_files() -> list[str]:
    return [f"missing required file: {path}" for path in REQUIRED_FILES if not path.exists()]


def validate_runbook() -> list[str]:
    errors: list[str] = []
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    for phrase in RUNBOOK_REQUIRED_PHRASES:
        if phrase not in text:
            errors.append(f"runbook missing required phrase: {phrase}")
    for phrase in FORBIDDEN_RUNBOOK_PHRASES:
        if phrase in text:
            errors.append(f"runbook contains forbidden overclaim phrase: {phrase}")
    return errors


def validate_readme() -> list[str]:
    text = README_PATH.read_text(encoding="utf-8")
    return [
        f"README missing deployment verification phrase: {phrase}"
        for phrase in README_REQUIRED_PHRASES
        if phrase not in text
    ]


def validate_all() -> list[str]:
    errors: list[str] = []
    errors.extend(validate_required_files())
    if not RUNBOOK_PATH.exists() or not README_PATH.exists():
        return errors
    errors.extend(validate_runbook())
    errors.extend(validate_readme())
    return errors


def main() -> int:
    errors = validate_all()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)  # noqa: T201
        return 1
    print("deployment verification assets OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
