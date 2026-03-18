"""
Win32 Hotkey Manager – Native Windows RegisterHotKey for global hotkeys.

Replaces the `keyboard` library with Windows API for:
- More reliable hotkey registration (no hooks)
- No external dependency needed
- Won't conflict with other applications
- Lower CPU overhead
"""

import ctypes
import logging
import threading
from collections.abc import Callable
from ctypes import wintypes

logger = logging.getLogger("HotkeyManager")

# Windows constants
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Virtual key codes
VK_CODES: dict[str, int] = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "ESC": 0x1B, "SPACE": 0x20, "RETURN": 0x0D, "TAB": 0x09,
    "BACK": 0x08, "DELETE": 0x2E, "INSERT": 0x2D,
    "HOME": 0x24, "END": 0x23,
    "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
}
# Add A-Z and 0-9
for c in range(ord("A"), ord("Z") + 1):
    VK_CODES[chr(c)] = c
for n in range(10):
    VK_CODES[str(n)] = 0x30 + n


def parse_hotkey(hotkey_str: str) -> tuple[int, int]:
    """Parse 'CTRL+SHIFT+F5' into (modifiers, vk_code)."""
    parts = [p.strip().upper() for p in hotkey_str.split("+")]
    modifiers = 0
    vk_code = 0

    for part in parts:
        if part in ("CTRL", "CONTROL"):
            modifiers |= MOD_CONTROL
        elif part == "ALT":
            modifiers |= MOD_ALT
        elif part == "SHIFT":
            modifiers |= MOD_SHIFT
        elif part in ("WIN", "WINDOWS"):
            modifiers |= MOD_WIN
        elif part in VK_CODES:
            vk_code = VK_CODES[part]
        else:
            raise ValueError(f"Unknown key: {part}")

    if vk_code == 0:
        raise ValueError(f"No main key in hotkey: {hotkey_str}")

    return modifiers | MOD_NOREPEAT, vk_code


class HotkeyManager:
    """
    Global hotkey manager using Windows RegisterHotKey.

    Usage:
        hk = HotkeyManager()
        hk.register("F6", on_play)
        hk.register("F7", on_pause)
        hk.start()
        ...
        hk.stop()
    """

    def __init__(self) -> None:
        self._hotkeys: dict[int, Callable[[], None]] = {}
        self._next_id = 1
        self._thread: threading.Thread | None = None
        self._running = False

    def register(self, hotkey: str, callback: Callable[[], None]) -> int:
        """Register a global hotkey. Returns hotkey ID."""
        modifiers, vk_code = parse_hotkey(hotkey)
        hid = self._next_id
        self._next_id += 1

        if not ctypes.windll.user32.RegisterHotKey(
            None, hid, modifiers, vk_code
        ):
            logger.error("Failed to register hotkey: %s", hotkey)
            return -1

        self._hotkeys[hid] = callback
        logger.info("Registered: %s (id=%d)", hotkey, hid)
        return hid

    def unregister(self, hotkey_id: int) -> None:
        if hotkey_id in self._hotkeys:
            ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
            del self._hotkeys[hotkey_id]

    def unregister_all(self) -> None:
        for hid in list(self._hotkeys.keys()):
            self.unregister(hid)

    def start(self) -> None:
        """Start hotkey listener thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._message_loop, daemon=True, name="HotkeyListener"
        )
        self._thread.start()
        logger.info("Hotkey listener started")

    def stop(self) -> None:
        """Stop listener and unregister all."""
        self._running = False
        self.unregister_all()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        logger.info("Hotkey listener stopped")

    def _message_loop(self) -> None:
        """Windows message loop for hotkey events."""
        msg = wintypes.MSG()
        while self._running:
            if ctypes.windll.user32.PeekMessageW(
                ctypes.byref(msg), None, 0, 0, 1
            ):
                if msg.message == WM_HOTKEY:
                    hid = msg.wParam
                    if hid in self._hotkeys:
                        try:
                            self._hotkeys[hid]()
                        except Exception as e:
                            logger.error("Hotkey callback error: %s", e)
            else:
                ctypes.windll.kernel32.Sleep(10)  # Avoid busy-wait
