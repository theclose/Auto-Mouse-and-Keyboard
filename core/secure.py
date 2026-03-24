"""
Secure variable storage using Windows DPAPI.

Encrypts sensitive data (passwords, tokens) so they are stored
encrypted in macro JSON files but decrypted at runtime.
"""

import base64
import logging

logger = logging.getLogger(__name__)

try:
    import win32crypt

    _HAS_DPAPI = True
except ImportError:
    _HAS_DPAPI = False
    logger.warning("win32crypt not available — secure vars will store plaintext")


def encrypt(plaintext: str) -> str:
    """Encrypt a string using Windows DPAPI. Returns base64-encoded blob."""
    if not _HAS_DPAPI:
        return plaintext
    try:
        blob = win32crypt.CryptProtectData(
            plaintext.encode("utf-8"),
            "AutoMacro",  # description
            None,  # optional entropy
            None,  # reserved
            None,  # prompt struct
            0,  # flags
        )
        return "DPAPI:" + base64.b64encode(blob).decode("ascii")
    except Exception as e:
        logger.error("Encryption failed: %s", e)
        return plaintext


def decrypt(ciphertext: str) -> str:
    """Decrypt a DPAPI-encrypted string."""
    if not _HAS_DPAPI or not ciphertext.startswith("DPAPI:"):
        return ciphertext
    try:
        blob = base64.b64decode(ciphertext[6:])
        _, plaintext_bytes = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        return plaintext_bytes.decode("utf-8")
    except Exception as e:
        logger.error("Decryption failed: %s", e)
        return ""


def is_encrypted(value: str) -> bool:
    """Check if a value is DPAPI-encrypted."""
    return isinstance(value, str) and value.startswith("DPAPI:")
