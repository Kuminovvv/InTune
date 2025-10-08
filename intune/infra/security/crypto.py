"""Helper utilities for local encryption of cached data."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet


class SecretBox:
    """Thin wrapper around Fernet for symmetric encryption."""

    def __init__(self, key_path: Path) -> None:
        self._key_path = key_path
        self._fernet = Fernet(self._load_or_create_key())

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        return self._fernet.decrypt(token)

    def _load_or_create_key(self) -> bytes:
        if self._key_path.exists():
            return self._key_path.read_bytes()
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        self._key_path.write_bytes(key)
        os.chmod(self._key_path, 0o600)
        return key


__all__ = ["SecretBox"]
