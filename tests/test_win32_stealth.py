"""
Tests for core.win32_stealth — Win32 stealth automation layer.

Tests use mocks for all Win32 API calls to avoid requiring a real
windowing environment.
"""

from unittest.mock import patch

import pytest

# ═══════════════════════════════════════════════════════
#  Coordinate helper
# ═══════════════════════════════════════════════════════


class TestMakeLParam:
    """Test LPARAM packing: (y << 16) | (x & 0xFFFF)."""

    def test_basic(self):
        from core.win32_stealth import _make_lparam
        assert _make_lparam(10, 20) == (20 << 16) | 10

    def test_zero(self):
        from core.win32_stealth import _make_lparam
        assert _make_lparam(0, 0) == 0

    def test_large_coords(self):
        from core.win32_stealth import _make_lparam
        result = _make_lparam(1920, 1080)
        # Unpack to verify
        x = result & 0xFFFF
        y = (result >> 16) & 0xFFFF
        assert x == 1920
        assert y == 1080

    def test_x_clamped_to_16bit(self):
        from core.win32_stealth import _make_lparam
        # x is masked to 16 bits
        result = _make_lparam(0xFFFF, 0)
        x = result & 0xFFFF
        assert x == 0xFFFF


# ═══════════════════════════════════════════════════════
#  Window validation
# ═══════════════════════════════════════════════════════


class TestIsWindowValid:
    """Tests for is_window_valid."""

    @patch("core.win32_stealth.user32")
    def test_valid_window(self, mock_user32):
        from core.win32_stealth import is_window_valid
        mock_user32.IsWindow.return_value = True
        assert is_window_valid(0x1234) is True

    @patch("core.win32_stealth.user32")
    def test_invalid_window(self, mock_user32):
        from core.win32_stealth import is_window_valid
        mock_user32.IsWindow.return_value = False
        assert is_window_valid(0) is False


# ═══════════════════════════════════════════════════════
#  Stealth Click
# ═══════════════════════════════════════════════════════


class TestStealthClick:
    """Tests for stealth_click message sequence."""

    @patch("core.win32_stealth.time.sleep")
    @patch("core.win32_stealth.user32")
    def test_left_click_sends_three_messages(self, mock_user32, mock_sleep):
        """Left click should send MOUSEMOVE → LBUTTONDOWN → LBUTTONUP."""
        from core.win32_stealth import (
            WM_LBUTTONDOWN,
            WM_LBUTTONUP,
            WM_MOUSEMOVE,
            stealth_click,
        )

        mock_user32.IsWindow.return_value = True
        mock_user32.PostMessageW.return_value = True

        stealth_click(0xABCD, 100, 200, right=False)

        calls = mock_user32.PostMessageW.call_args_list
        assert len(calls) == 3

        # MOUSEMOVE first
        assert calls[0][0][1] == WM_MOUSEMOVE
        # LBUTTONDOWN
        assert calls[1][0][1] == WM_LBUTTONDOWN
        # LBUTTONUP
        assert calls[2][0][1] == WM_LBUTTONUP

    @patch("core.win32_stealth.time.sleep")
    @patch("core.win32_stealth.user32")
    def test_right_click_sends_rb_messages(self, mock_user32, mock_sleep):
        """Right click should use WM_RBUTTONDOWN/UP."""
        from core.win32_stealth import (
            WM_RBUTTONDOWN,
            WM_RBUTTONUP,
            stealth_click,
        )

        mock_user32.IsWindow.return_value = True
        mock_user32.PostMessageW.return_value = True

        stealth_click(0xABCD, 50, 60, right=True)

        calls = mock_user32.PostMessageW.call_args_list
        assert calls[1][0][1] == WM_RBUTTONDOWN
        assert calls[2][0][1] == WM_RBUTTONUP

    @patch("core.win32_stealth.user32")
    def test_invalid_hwnd_raises(self, mock_user32):
        from core.win32_stealth import stealth_click
        mock_user32.IsWindow.return_value = False
        with pytest.raises(ValueError, match="Invalid window handle"):
            stealth_click(0, 0, 0)

    @patch("core.win32_stealth.time.sleep")
    @patch("core.win32_stealth.user32")
    def test_humanized_delay(self, mock_user32, mock_sleep):
        """Should have delays between messages for anti-detection."""
        from core.win32_stealth import stealth_click
        mock_user32.IsWindow.return_value = True
        mock_user32.PostMessageW.return_value = True

        stealth_click(0x1, 10, 20)

        # At least 2 sleep calls (10ms settle + random hold)
        assert mock_sleep.call_count >= 2


# ═══════════════════════════════════════════════════════
#  Stealth Double Click
# ═══════════════════════════════════════════════════════


class TestStealthDoubleClick:

    @patch("core.win32_stealth.time.sleep")
    @patch("core.win32_stealth.user32")
    def test_sends_dblclk_message(self, mock_user32, mock_sleep):
        from core.win32_stealth import WM_LBUTTONDBLCLK, stealth_double_click
        mock_user32.IsWindow.return_value = True
        mock_user32.PostMessageW.return_value = True

        stealth_double_click(0x1, 10, 20)

        msgs = [c[0][1] for c in mock_user32.PostMessageW.call_args_list]
        assert WM_LBUTTONDBLCLK in msgs


# ═══════════════════════════════════════════════════════
#  Stealth Keyboard
# ═══════════════════════════════════════════════════════


class TestStealthTypeText:

    @patch("core.win32_stealth.time.sleep")
    @patch("core.win32_stealth.user32")
    def test_types_each_char(self, mock_user32, mock_sleep):
        from core.win32_stealth import WM_CHAR, stealth_type_text
        mock_user32.IsWindow.return_value = True
        mock_user32.PostMessageW.return_value = True

        stealth_type_text(0x1, "ABC", delay_ms=0)

        calls = mock_user32.PostMessageW.call_args_list
        assert len(calls) == 3
        # Each char sent as WM_CHAR with ord(char)
        assert all(c[0][1] == WM_CHAR for c in calls)
        assert calls[0][0][2] == ord("A")
        assert calls[1][0][2] == ord("B")
        assert calls[2][0][2] == ord("C")

    @patch("core.win32_stealth.user32")
    def test_invalid_hwnd_raises(self, mock_user32):
        from core.win32_stealth import stealth_type_text
        mock_user32.IsWindow.return_value = False
        with pytest.raises(ValueError):
            stealth_type_text(0, "test")

    @patch("core.win32_stealth.time.sleep")
    @patch("core.win32_stealth.user32")
    def test_delay_between_keys(self, mock_user32, mock_sleep):
        from core.win32_stealth import stealth_type_text
        mock_user32.IsWindow.return_value = True
        mock_user32.PostMessageW.return_value = True

        stealth_type_text(0x1, "AB", delay_ms=50)

        # Each char should trigger a 50ms sleep
        sleep_calls = [c for c in mock_sleep.call_args_list
                       if c[0][0] == pytest.approx(0.05)]
        assert len(sleep_calls) == 2


class TestStealthSendKey:

    @patch("core.win32_stealth.time.sleep")
    @patch("core.win32_stealth.user32")
    def test_sends_keydown_keyup(self, mock_user32, mock_sleep):
        from core.win32_stealth import WM_KEYDOWN, WM_KEYUP, stealth_send_key
        mock_user32.IsWindow.return_value = True
        mock_user32.PostMessageW.return_value = True

        stealth_send_key(0x1, 0x0D)  # VK_RETURN

        calls = mock_user32.PostMessageW.call_args_list
        assert calls[0][0][1] == WM_KEYDOWN
        assert calls[1][0][1] == WM_KEYUP
        assert calls[0][0][2] == 0x0D


# ═══════════════════════════════════════════════════════
#  Window Discovery
# ═══════════════════════════════════════════════════════


class TestGetWindowTitle:

    @patch("core.win32_stealth.user32")
    def test_empty_title(self, mock_user32):
        from core.win32_stealth import get_window_title
        mock_user32.GetWindowTextLengthW.return_value = 0
        assert get_window_title(0x1) == ""


# ═══════════════════════════════════════════════════════
#  Action classes (integration-level)
# ═══════════════════════════════════════════════════════


class TestStealthClickAction:
    """Test the StealthClick action class from modules/mouse.py."""

    def test_serialization_roundtrip(self):
        from modules.mouse import StealthClick
        action = StealthClick(
            x=100, y=200,
            window_title="Notepad",
            right_click=True,
            double_click=False,
        )
        params = action._get_params()
        assert params == {
            "x": 100, "y": 200,
            "window_title": "Notepad",
            "right_click": True,
            "double_click": False,
        }

        # Roundtrip
        new_action = StealthClick()
        new_action._set_params(params)
        assert new_action.x == 100
        assert new_action.y == 200
        assert new_action.window_title == "Notepad"
        assert new_action.right_click is True

    def test_display_name(self):
        from modules.mouse import StealthClick
        action = StealthClick(x=50, y=70, window_title="My App")
        name = action.get_display_name()
        assert "Stealth" in name
        assert "50" in name
        assert "70" in name

    @patch("core.win32_stealth.find_window_by_title", return_value=None)
    def test_execute_window_not_found(self, mock_find):
        from modules.mouse import StealthClick
        action = StealthClick(x=0, y=0, window_title="NonExistent")
        result = action.execute()
        assert result is False

    def test_execute_no_title(self):
        from modules.mouse import StealthClick
        action = StealthClick(x=0, y=0, window_title="")
        result = action.execute()
        assert result is False


class TestStealthTypeAction:

    def test_serialization_roundtrip(self):
        from modules.mouse import StealthType
        action = StealthType(
            text="Hello World",
            window_title="Notepad",
            key_delay_ms=50,
        )
        params = action._get_params()
        assert params["text"] == "Hello World"
        assert params["key_delay_ms"] == 50

    def test_display_name_truncation(self):
        from modules.mouse import StealthType
        action = StealthType(
            text="A" * 50,
            window_title="Very Long Window Title That Should Truncate",
        )
        name = action.get_display_name()
        assert "…" in name  # Should truncate

    @patch("core.win32_stealth.find_window_by_title", return_value=None)
    def test_execute_window_not_found(self, mock_find):
        from modules.mouse import StealthType
        action = StealthType(text="test", window_title="NonExistent")
        result = action.execute()
        assert result is False
