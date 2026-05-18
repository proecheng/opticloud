"""Unit tests for auth_service.security (HMAC API Key + JWT Ed25519)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from auth_service import security
from auth_service.config import settings


def test_generate_api_key_format() -> None:
    full_key, prefix, hmac_hash = security.generate_api_key()
    assert full_key.startswith("sk-")
    assert len(full_key) > 40  # 32 bytes urlsafe → ~43 chars + "sk-"
    assert prefix == full_key[:6]
    assert len(hmac_hash) == 64  # SHA256 hex


def test_verify_api_key_roundtrip() -> None:
    full_key, _prefix, hmac_hash = security.generate_api_key()
    assert security.verify_api_key(full_key, hmac_hash, stored_pepper_version=1) is True
    assert security.verify_api_key("sk-wrong-key", hmac_hash, stored_pepper_version=1) is False


def test_jwt_access_token_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT Ed25519 sign + verify roundtrip."""
    # Use tmp keys to avoid polluting repo
    monkeypatch.setattr(settings, "jwt_private_key_path", str(tmp_path / "jwt.key"))
    monkeypatch.setattr(settings, "jwt_public_key_path", str(tmp_path / "jwt.pub"))

    # Reset key cache
    security._jwt_private_key = None
    security._jwt_public_key = None

    user_id = uuid.uuid4()
    token = security.create_access_token(user_id, scopes=["optimize:write"])
    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # header.payload.signature

    payload = security.verify_jwt(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert payload["scopes"] == ["optimize:write"]


def test_jwt_refresh_token_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_private_key_path", str(tmp_path / "jwt.key"))
    monkeypatch.setattr(settings, "jwt_public_key_path", str(tmp_path / "jwt.pub"))
    security._jwt_private_key = None
    security._jwt_public_key = None

    user_id = uuid.uuid4()
    refresh = security.create_refresh_token(user_id)
    payload = security.verify_jwt(refresh)
    assert payload["type"] == "refresh"
