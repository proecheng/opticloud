"""Shared JWT verification (D1 fix — extracted from auth-service for reuse).

Used by:
- auth-service (own tokens)
- billing-service (verify auth-issued tokens; Story 5.A.1)
- future: solver-orchestrator, chat-service, etc.

The signing/issuing logic stays in auth-service (private key never leaves).
This module only does VERIFICATION (public key, signature check, claims decode).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class JWTVerifyError(Exception):
    """Raised when JWT verification fails (any reason)."""


class PublicKeyLoader:
    """Lazy public-key loader that caches in-process.

    Usage:
        loader = PublicKeyLoader("/path/to/jwt_public.pem")
        claims = verify_jwt(token, loader.load())

    Raises FileNotFoundError on first .load() if PEM file missing.
    """

    def __init__(self, public_key_path: str | Path) -> None:
        self._path = Path(public_key_path)
        self._key: Ed25519PublicKey | None = None

    def load(self) -> Ed25519PublicKey:
        if self._key is None:
            if not self._path.exists() or self._path.stat().st_size == 0:
                raise FileNotFoundError(
                    f"JWT public key missing or empty at {self._path}. "
                    "auth-service must run first to generate the keypair."
                )
            pem = self._path.read_bytes()
            loaded = serialization.load_pem_public_key(pem)
            if not isinstance(loaded, Ed25519PublicKey):
                raise JWTVerifyError(
                    f"unexpected key type at {self._path}: {type(loaded).__name__}"
                )
            self._key = loaded
        return self._key


def verify_jwt(token: str, public_key: Ed25519PublicKey) -> dict[str, Any]:
    """Verify EdDSA JWT signature and decode claims.

    Args:
        token: the bearer token string (no "Bearer " prefix)
        public_key: loaded Ed25519PublicKey

    Returns: decoded claims dict (sub, iat, exp, type, scopes, ...)

    Raises:
        JWTVerifyError: on any verification failure (bad sig / expired / malformed)
    """
    try:
        return jwt.decode(token, public_key, algorithms=["EdDSA"])  # type: ignore[no-any-return]
    except jwt.PyJWTError as e:
        raise JWTVerifyError(str(e)) from e
