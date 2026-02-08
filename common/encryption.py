"""
Field-level encryption for sensitive data (bank accounts, ID numbers).
Uses Fernet symmetric encryption with a key from settings.
"""

import base64
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

_fernet_instance = None


def _get_fernet():
    global _fernet_instance
    if _fernet_instance is None:
        key = settings.FIELD_ENCRYPTION_KEY
        if not key:
            raise ValueError("FIELD_ENCRYPTION_KEY is not set. Cannot encrypt/decrypt sensitive data.")
        # Ensure key is valid base64
        try:
            _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            raise ValueError(f"Invalid FIELD_ENCRYPTION_KEY: {e}") from e
    return _fernet_instance


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext. Returns plaintext string."""
    if not ciphertext:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt value. Key may have rotated.")
        raise ValueError("Decryption failed. Data may be corrupted or key has changed.")

