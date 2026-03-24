"""
Win32 Hotkey Manager – Native Windows RegisterHotKey for global hotkeys.

IMPORTANT: RegisterHotKey(NULL, ...) is thread-affine – WM_HOTKEY messages
are posted to the registering thread's message queue. Therefore all
registration/unregistration MUST happen inside the listener thread.
"""

import ctypes
import logging
import threading
from collections.abc import Callable
from ctypes import wintypes

logger = logging.getLogger("HotkeyManager")

# Windows constants
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_APP = 0x8000
WM_APP_REGISTER = WM_APP + 1  # custom: trigger pending registration
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Virtual key codes
VK_CODES: dict[str, int] = {
    "F1": 0x70,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F5": 0x74,
    "F6": 0x75,
    "F7": 0x76,
    "F8": 0x77,
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
    "ESC": 0x1B,
    "SPACE": 0x20,
    "RETURN": 0x0D,
    "TAB": 0x09,
    "BACK": 0x08,
    "DELETE": 0x2E,
    "INSERT": 0x2D,
    "HOME": 0x24,
    "END": 0x23,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
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

    All RegisterHotKey/UnregisterHotKey calls happen inside the listener
    thread to ensure WM_HOTKEY messages are delivered to the correct
    thread message queue.

    Usage:
        hk = HotkeyManager()
        hk.register("F6", on_play)
        hk.register("F7", on_pause)
        hk.start()   # registrations happen here, in the listener thread
        ...
        hk.stop()
    """

    def __init__(self) -> None:
        self._hotkeys: dict[int, Callable[[], None]] = {}
        self._pending: list[tuple[str, int, int, Callable[[], None], int]] = []
        self._next_id = 1
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._running = False
        self._lock = threading.Lock()

    def register(self, hotkey: str, callback: Callable[[], None]) -> int:
        """Queue a global hotkey for registration. Returns hotkey ID.

        Actual Win32 registration happens in the listener thread.
        """
        modifiers, vk_code = parse_hotkey(hotkey)
        hid = self._next_id
        self._next_id += 1
        with self._lock:
            self._pending.append((hotkey, modifiers, vk_code, callback, hid))
        # If already running, wake the listener thread to process pending
        if self._running and self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_APP_REGISTER, 0, 0)
        return hid

    def start(self) -> None:
        """Start hotkey listener thread (also performs pending registrations)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._message_loop, daemon=True, name="HotkeyListener")
        self._thread.start()

    def stop(self) -> None:
        """Stop listener and unregister all hotkeys."""
        self._running = False
        # Post WM_QUIT to wake the listener thread so it can exit
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._thread_id = None
        logger.info("Hotkey listener stopped")

    def _process_pending(self) -> None:
        """Register all pending hotkeys (must be called from listener thread)."""
        with self._lock:
            pending = list(self._pending)
            self._pending.clear()
        for hotkey, modifiers, vk_code, callback, hid in pending:
            if ctypes.windll.user32.RegisterHotKey(None, hid, modifiers, vk_code):
                self._hotkeys[hid] = callback
                logger.info("Registered: %s (id=%d)", hotkey, hid)
            else:
                logger.error("Failed to register hotkey: %s", hotkey)

    def _unregister_all(self) -> None:
        """Unregister all hotkeys (must be called from listener thread)."""
        for hid in list(self._hotkeys.keys()):
            ctypes.windll.user32.UnregisterHotKey(None, hid)
        self._hotkeys.clear()

    def _message_loop(self) -> None:
        """Windows message loop for hotkey events.

        Runs entirely in the listener thread — registration, message
        processing, and unregistration all happen here.
        """
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        # Register all pending hotkeys from THIS thread
        self._process_pending()
        logger.info("Hotkey listener started")

        msg = wintypes.MSG()
        while self._running:
            if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == WM_HOTKEY:
                    hid = msg.wParam
                    if hid in self._hotkeys:
                        try:
                            self._hotkeys[hid]()
                        except Exception as e:
                            logger.error("Hotkey callback error: %s", e)
                elif msg.message == WM_APP_REGISTER:
                    # New hotkeys queued — register them
                    self._process_pending()
                elif msg.message == WM_QUIT:
                    break
            else:
                ctypes.windll.kernel32.Sleep(10)  # Avoid busy-wait

        # Unregister from this thread before exiting
        self._unregister_all()
