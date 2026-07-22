"""Backup encryption.

Uses a single master key (Fernet / AES-128-CBC + HMAC) taken from the
environment. The key is NEVER stored in the DB or emailed. Files are written
with a ``.enc`` suffix; recovery only needs this key, which the operator keeps
in their secrets manager / deploy env.
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet
from django.conf import settings

logger = logging.getLogger("apps.backups")


def _fernet() -> Fernet:
    key = settings.BACKUP_ENCRYPTION_KEY
    if key:
        return Fernet(key.encode() if isinstance(key, str) else key)
    # Dev fallback: derive a stable key from SECRET_KEY so local runs work.
    # Production MUST set BACKUP_ENCRYPTION_KEY (checked in prod settings).
    logger.warning("BACKUP_ENCRYPTION_KEY not set — deriving a dev key from SECRET_KEY.")
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet().decrypt(token)


def generate_key() -> str:
    """Convenience for operators: print a fresh key to put in the env."""
    return Fernet.generate_key().decode()
