"""
Sprint 1: Tests for core/retry.py and core/secure.py.

Run: python -m pytest tests/test_retry_secure.py -v
"""

import os
import sys
import time
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 1. Retry decorator
# ============================================================

class TestRetryDecorator:
    """Test core.retry.retry decorator."""

    def test_succeeds_first_try(self) -> None:
        from core.retry import retry

        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def ok() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        assert ok() == "success"
        assert call_count == 1

    def test_retries_on_failure(self) -> None:
        from core.retry import retry

        call_count = 0

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "ok"

        assert flaky() == "ok"
        assert call_count == 3

    def test_raises_after_max_attempts(self) -> None:
        from core.retry import retry

        @retry(max_attempts=2, delay=0.01, exceptions=(RuntimeError,))
        def always_fails() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            always_fails()

    def test_backoff_increases_delay(self) -> None:
        from core.retry import retry

        timestamps: list[float] = []

        @retry(max_attempts=3, delay=0.05, backoff=2.0, exceptions=(IOError,))
        def timed_fail() -> None:
            timestamps.append(time.perf_counter())
            raise IOError("fail")

        with pytest.raises(IOError):
            timed_fail()

        # 3 attempts → 2 delays: ~0.05s then ~0.10s
        assert len(timestamps) == 3
        d1 = timestamps[1] - timestamps[0]
        d2 = timestamps[2] - timestamps[1]
        assert d1 >= 0.04  # first delay ~0.05s
        assert d2 >= 0.08  # second delay ~0.10s (2x backoff)

    def test_only_catches_specified_exceptions(self) -> None:
        from core.retry import retry

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def type_error() -> None:
            raise TypeError("wrong type")

        # TypeError is NOT in exceptions → should not retry
        with pytest.raises(TypeError):
            type_error()

    def test_preserves_function_metadata(self) -> None:
        from core.retry import retry

        @retry(max_attempts=3, delay=0.01)
        def my_func() -> None:
            """My docstring."""
            pass

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."


# ============================================================
# 2. Secure module
# ============================================================

class TestSecureModule:
    """Test core.secure encrypt/decrypt/is_encrypted."""

    def test_is_encrypted_true(self) -> None:
        from core.secure import is_encrypted
        assert is_encrypted("DPAPI:abc123") is True

    def test_is_encrypted_false(self) -> None:
        from core.secure import is_encrypted
        assert is_encrypted("plain text") is False
        assert is_encrypted("") is False

    def test_is_encrypted_non_string(self) -> None:
        from core.secure import is_encrypted
        assert is_encrypted(123) is False  # type: ignore

    def test_encrypt_without_dpapi_returns_plaintext(self) -> None:
        from core import secure
        old = secure._HAS_DPAPI
        try:
            secure._HAS_DPAPI = False
            result = secure.encrypt("hello")
            assert result == "hello"
        finally:
            secure._HAS_DPAPI = old

    def test_decrypt_without_dpapi_returns_as_is(self) -> None:
        from core import secure
        old = secure._HAS_DPAPI
        try:
            secure._HAS_DPAPI = False
            assert secure.decrypt("hello") == "hello"
        finally:
            secure._HAS_DPAPI = old

    def test_decrypt_non_dpapi_prefix_returns_as_is(self) -> None:
        from core.secure import decrypt
        assert decrypt("plain text") == "plain text"

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """If DPAPI is available, test full round-trip."""
        from core import secure
        if not secure._HAS_DPAPI:
            pytest.skip("DPAPI not available")
        text = "my_secret_password_123"
        encrypted = secure.encrypt(text)
        assert encrypted.startswith("DPAPI:")
        decrypted = secure.decrypt(encrypted)
        assert decrypted == text

    def test_encrypt_error_returns_plaintext(self) -> None:
        from core import secure
        old = secure._HAS_DPAPI
        try:
            secure._HAS_DPAPI = True
            with patch('core.secure.win32crypt') as mock_crypt:
                mock_crypt.CryptProtectData.side_effect = Exception("fail")
                result = secure.encrypt("test")
            assert result == "test"  # fallback to plaintext
        finally:
            secure._HAS_DPAPI = old
