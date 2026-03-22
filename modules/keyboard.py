"""
Keyboard automation actions.
Provides key press, key combo, text typing, and hotkey actions.
"""

import ctypes
import logging
import time
import pyautogui
from typing import Any

from core.action import Action, register_action

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Win32 SendInput for Unicode text (no clipboard interference)
# ---------------------------------------------------------------------------
_INPUT_KEYBOARD = 1
_KEYEVENTF_UNICODE = 0x0004
_KEYEVENTF_KEYUP = 0x0002


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),  # ULONG_PTR (8 bytes on 64-bit)
    ]


class _MOUSEINPUT(ctypes.Structure):
    """Placeholder for union sizing – matches MOUSEINPUT in WinUser.h."""
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", _INPUTUNION),
    ]


def _send_unicode_string(text: str, interval: float = 0.02) -> None:
    """Type Unicode text using Win32 SendInput with VK_PACKET."""
    _sizeof_input = ctypes.sizeof(_INPUT)

    if interval <= 0:
        # Fast path: batch all chars into one SendInput call
        n = len(text) * 2
        inputs = (_INPUT * n)()
        for i, char in enumerate(text):
            code = ord(char)
            idx = i * 2
            inputs[idx].type = _INPUT_KEYBOARD
            inputs[idx].union.ki.wScan = code
            inputs[idx].union.ki.dwFlags = _KEYEVENTF_UNICODE
            inputs[idx + 1].type = _INPUT_KEYBOARD
            inputs[idx + 1].union.ki.wScan = code
            inputs[idx + 1].union.ki.dwFlags = (
                _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP
            )
        ctypes.windll.user32.SendInput(n, inputs, _sizeof_input)
    else:
        # Per-char with interval: reuse a single 2-element array
        pair = (_INPUT * 2)()
        pair[0].type = _INPUT_KEYBOARD
        pair[0].union.ki.dwFlags = _KEYEVENTF_UNICODE
        pair[1].type = _INPUT_KEYBOARD
        pair[1].union.ki.dwFlags = _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP
        for char in text:
            code = ord(char)
            pair[0].union.ki.wScan = code
            pair[1].union.ki.wScan = code
            ctypes.windll.user32.SendInput(2, pair, _sizeof_input)
            time.sleep(interval)


@register_action("key_press")
class KeyPress(Action):
    """Press and release a single key."""

    def __init__(self, key: str = "enter", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.key = key

    def execute(self) -> bool:
        pyautogui.press(self.key)
        logger.debug("Pressed key: %s", self.key)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"key": self.key}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.key = params.get("key", "enter")

    def get_display_name(self) -> str:
        return f"Press [{self.key}]"


@register_action("key_combo")
class KeyCombo(Action):
    """
    Press a key combination (e.g., Ctrl+C, Alt+F4).
    Keys are specified as a list: ["ctrl", "c"]
    """

    def __init__(self, keys: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.keys = list(keys) if keys else ["ctrl", "c"]

    def execute(self) -> bool:
        pyautogui.hotkey(*self.keys)
        logger.debug("Key combo: %s", "+".join(self.keys))
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"keys": self.keys}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.keys = params.get("keys", ["ctrl", "c"])

    def get_display_name(self) -> str:
        return f"Combo [{'+'.join(self.keys)}]"


@register_action("type_text")
class TypeText(Action):
    """Type a string of text character by character."""

    def __init__(self, text: str = "", interval: float = 0.02, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.text = text
        self.interval = interval  # seconds between each character

    def execute(self) -> bool:
        from core.engine_context import get_context
        text = self.text
        # Template interpolation: ${var_name} → value
        ctx = get_context()
        if ctx and '${' in text:
            text = ctx.interpolate(text)
        if text.isascii():
            pyautogui.typewrite(text, interval=self.interval)
        else:
            _send_unicode_string(text, self.interval)
        logger.debug("Typed text: '%s'", text[:50])
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"text": self.text, "interval": self.interval}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.text = params.get("text", "")
        self.interval = params.get("interval", 0.02)

    def get_display_name(self) -> str:
        preview = self.text[:30] + ("…" if len(self.text) > 30 else "")
        return f'Type "{preview}"'


@register_action("hotkey")
class HotKey(Action):
    """
    Press a global hotkey combination.
    Alias for KeyCombo but with a friendlier name for the UI.
    """

    def __init__(self, keys: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.keys = list(keys) if keys else []

    def execute(self) -> bool:
        if self.keys:
            pyautogui.hotkey(*self.keys)
            logger.debug("Hotkey: %s", "+".join(self.keys))
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"keys": self.keys}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.keys = params.get("keys", [])

    def get_display_name(self) -> str:
        return f"Hotkey [{'+'.join(self.keys)}]" if self.keys else "Hotkey []"


# List of all supported special key names for UI dropdowns
SPECIAL_KEYS = [
    "enter", "tab", "space", "backspace", "delete", "escape",
    "up", "down", "left", "right",
    "home", "end", "pageup", "pagedown",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "shift", "ctrl", "alt", "win",
    "capslock", "numlock", "printscreen", "insert",
    "volumeup", "volumedown", "volumemute",
]
