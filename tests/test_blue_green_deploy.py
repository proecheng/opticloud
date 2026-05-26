from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_blue_green_deploy.py"
SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy" / "blue-green.sh"
BLUE_COMPOSE_PATH = REPO_ROOT / "docker-compose.blue.yml"
GREEN_COMPOSE_PATH = REPO_ROOT / "docker-compose.green.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_blue_green_deploy", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def _load_compose(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return copy.deepcopy(data)


def _assert_invalid(
    script_text: str | None = None,
    blue_compose: dict[str, Any] | None = None,
    green_compose: dict[str, Any] | None = None,
    expected: str = "",
    source_texts: dict[str, str] | None = None,
) -> None:
    validator = _load_validator()
    errors = validator.validate_assets(
        script_text or _load_script(),
        blue_compose or _load_compose(BLUE_COMPOSE_PATH),
        green_compose or _load_compose(GREEN_COMPOSE_PATH),
        source_texts,
    )
    assert any(expected in error for error in errors), errors


def test_committed_blue_green_assets_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "blue/green deploy assets OK" in result.stdout


def test_missing_rollback_command_is_rejected() -> None:
    script_text = _load_script().replace("    rollback)\n", "    revert)\n")

    _assert_invalid(script_text=script_text, expected="missing rollback command dispatch")


def test_deploy_stop_before_health_is_rejected() -> None:
    script_text = _load_script().replace(
        '  compose_up "${inactive}" "${image_tag}"\n'
        '  wait_for_health "${inactive}"\n'
        '  switch_traffic "${inactive}"\n'
        '  write_state "${inactive}" "${image_tag}" "${active}" "${active_image_tag}"\n'
        '  compose_stop "${active}"\n',
        '  compose_up "${inactive}" "${image_tag}"\n'
        '  compose_stop "${active}"\n'
        '  wait_for_health "${inactive}"\n'
        '  switch_traffic "${inactive}"\n'
        '  write_state "${inactive}" "${image_tag}" "${active}" "${active_image_tag}"\n',
    )

    _assert_invalid(script_text=script_text, expected="deploy flow must start inactive")


def test_mismatched_services_are_rejected() -> None:
    green_compose = _load_compose(GREEN_COMPOSE_PATH)
    del green_compose["services"]["solver-orchestrator"]

    _assert_invalid(green_compose=green_compose, expected="blue/green services must match")


def test_duplicate_blue_green_host_ports_are_rejected() -> None:
    green_compose = _load_compose(GREEN_COMPOSE_PATH)
    green_compose["services"]["web"]["ports"] = ["${GREEN_WEB_PORT:-3001}:3000"]

    _assert_invalid(green_compose=green_compose, expected="host ports must be distinct")


def test_duplicate_ports_within_one_manifest_are_rejected() -> None:
    blue_compose = _load_compose(BLUE_COMPOSE_PATH)
    blue_compose["services"]["api-gateway"]["ports"] = ["${BLUE_API_GATEWAY_PORT:-3001}:8000"]

    _assert_invalid(blue_compose=blue_compose, expected="host port 3001 reused")


def test_embedded_secret_environment_is_rejected() -> None:
    blue_compose = _load_compose(BLUE_COMPOSE_PATH)
    blue_compose["services"]["api-gateway"]["environment"]["API_TOKEN"] = "hardcoded"

    _assert_invalid(blue_compose=blue_compose, expected="forbidden secret-like env key API_TOKEN")


def test_forbidden_kubernetes_scope_drift_is_rejected() -> None:
    source_texts = {
        "scripts/deploy/blue-green.sh": _load_script() + "\nkubectl apply -f infra/k8s\n",
        "docker-compose.blue.yml": BLUE_COMPOSE_PATH.read_text(encoding="utf-8"),
        "docker-compose.green.yml": GREEN_COMPOSE_PATH.read_text(encoding="utf-8"),
    }

    _assert_invalid(source_texts=source_texts, expected="out-of-scope Kubernetes command")
