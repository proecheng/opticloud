"""Security utilities — API Key HMAC-SHA256 + JWT Ed25519.

Architecture references:
- D7: HMAC-SHA256 with Vault pepper (API Key)
- D8: EdDSA (Ed25519) JWT (15min access + 7day refresh)
- CRG4: pepper 季度 Vault HSM 轮换 + grace 30d 双 pepper
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from auth_service.config import settings

# ===== API Key Generation (FR A2 + D7) =====

API_KEY_PREFIX = "sk-"  # pragma: allowlist secret
API_KEY_PREFIX_VISIBLE_LEN = 6  # PRD §1079 前缀 6 位可见


def generate_api_key() -> tuple[str, str, str]:
    """Generate new API key, return (full_key, prefix, hmac_hash).

    Returns:
        full_key: "sk-XXXXX..." — only returned once at creation, never persisted
        prefix: "sk-XXX" first 6 chars (PRD §1079)
        hmac_hash: HMAC-SHA256(pepper, full_key) hex digest (persisted to DB)
    """
    # 32 bytes secure random → 43-char URL-safe base64
    raw = secrets.token_urlsafe(32)
    full_key = f"{API_KEY_PREFIX}{raw}"
    prefix = full_key[:API_KEY_PREFIX_VISIBLE_LEN]
    hmac_hash = _hmac_sha256(full_key, pepper_version=settings.api_key_pepper_version)
    return full_key, prefix, hmac_hash


def verify_api_key(full_key: str, stored_hash: str, stored_pepper_version: int) -> bool:
    """Verify API key against stored hash (CRG4 multi-pepper grace).

    During pepper rotation grace period, hash may use old or new pepper version.
    """
    computed = _hmac_sha256(full_key, pepper_version=stored_pepper_version)
    return hmac.compare_digest(computed, stored_hash)


def _hmac_sha256(full_key: str, pepper_version: int) -> str:
    """HMAC-SHA256(pepper, full_key) → hex digest.

    pepper_version: 1 = current; 2+ = future rotation grace (CRG4).
    Production: pepper from Vault HSM; dev: from env var.
    """
    # For now, use single dev pepper; production will look up Vault by version.
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    return hmac.new(pepper, full_key.encode("utf-8"), hashlib.sha256).hexdigest()


# ===== Guardian Consent Token Hashing (FR A10) =====


def generate_guardian_consent_token() -> str:
    """Generate a URL-safe one-time guardian consent token."""
    return secrets.token_urlsafe(32)


def hash_guardian_consent_token(token: str) -> str:
    """HMAC-SHA256 guardian consent token hash for DB persistence."""
    pepper = settings.guardian_consent_token_pepper_dev.encode("utf-8")
    return hmac.new(pepper, token.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_guardian_consent_token(token: str, stored_hash: str) -> bool:
    """Constant-time guardian consent token verification."""
    computed = hash_guardian_consent_token(token)
    return hmac.compare_digest(computed, stored_hash)


# ===== JWT Ed25519 (D8) =====

_jwt_private_key: Ed25519PrivateKey | None = None
_jwt_public_key: Ed25519PublicKey | None = None


def _load_jwt_keys() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Load JWT key pair from disk (dev) or Vault (prod, future)."""
    global _jwt_private_key, _jwt_public_key

    if _jwt_private_key is not None and _jwt_public_key is not None:
        return _jwt_private_key, _jwt_public_key

    private_path = Path(settings.jwt_private_key_path)
    public_path = Path(settings.jwt_public_key_path)

    # Dev fallback: generate ephemeral key pair if missing
    if not private_path.exists() or not public_path.exists():
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private_key = Ed25519PrivateKey.generate()
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        private_path.write_bytes(private_pem)
        public_path.write_bytes(public_pem)

    private_pem = private_path.read_bytes()
    public_pem = public_path.read_bytes()

    _jwt_private_key = serialization.load_pem_private_key(private_pem, password=None)  # type: ignore[assignment]
    _jwt_public_key = serialization.load_pem_public_key(public_pem)  # type: ignore[assignment]

    assert isinstance(_jwt_private_key, Ed25519PrivateKey)
    assert isinstance(_jwt_public_key, Ed25519PublicKey)
    return _jwt_private_key, _jwt_public_key


def create_access_token(user_id: uuid.UUID, scopes: list[str] | None = None) -> str:
    """Create short-lived (15min) JWT access token."""
    private_key, _ = _load_jwt_keys()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_access_ttl_minutes)).timestamp()),
        "type": "access",
        "scopes": scopes or [],
    }
    return jwt.encode(payload, private_key, algorithm="EdDSA")  # type: ignore[arg-type]


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Create long-lived (7day) JWT refresh token."""
    private_key, _ = _load_jwt_keys()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.jwt_refresh_ttl_days)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, private_key, algorithm="EdDSA")  # type: ignore[arg-type]


def verify_jwt(token: str) -> dict:  # type: ignore[type-arg]
    """Verify JWT signature and decode payload. Raises if invalid."""
    _, public_key = _load_jwt_keys()
    return jwt.decode(token, public_key, algorithms=["EdDSA"])  # type: ignore[arg-type,no-any-return]
