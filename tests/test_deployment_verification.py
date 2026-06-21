from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_deployment_verification.py"
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "staging-deployment-verification.md"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_deployment_verification", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_deployment_verification_assets_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "deployment verification assets OK" in result.stdout


def test_runbook_keeps_static_and_live_boundaries_explicit() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert "staging verification readiness" in runbook
    assert "does not claim that production is deployed" in runbook
    assert "Static manifest validation only" not in runbook
    assert "This is static manifest validation only." in runbook
    assert "Do not call static validation \"production verified\"" in runbook
    assert "Do not commit staging URLs" in runbook


def test_validator_rejects_missing_runbook_boundary_phrase(monkeypatch) -> None:
    validator = _load_validator()
    original = RUNBOOK_PATH.read_text(encoding="utf-8")
    modified = original.replace("staging verification readiness", "deployment proof")
    temp_runbook = RUNBOOK_PATH.parent / "staging-deployment-verification.tmp.md"
    temp_runbook.write_text(modified, encoding="utf-8")
    monkeypatch.setattr(validator, "RUNBOOK_PATH", temp_runbook)

    try:
        errors = validator.validate_runbook()
        assert any("staging verification readiness" in error for error in errors)
    finally:
        temp_runbook.unlink(missing_ok=True)


def test_validator_rejects_production_overclaim(monkeypatch) -> None:
    validator = _load_validator()
    original = RUNBOOK_PATH.read_text(encoding="utf-8")
    modified = original + "\nstatus: production verified\n"
    temp_runbook = RUNBOOK_PATH.parent / "staging-deployment-verification.tmp.md"
    temp_runbook.write_text(modified, encoding="utf-8")
    monkeypatch.setattr(validator, "RUNBOOK_PATH", temp_runbook)

    try:
        errors = validator.validate_runbook()
        assert any("forbidden overclaim phrase" in error for error in errors)
    finally:
        temp_runbook.unlink(missing_ok=True)
