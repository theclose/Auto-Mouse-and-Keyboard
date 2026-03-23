"""
Recorder – captures live mouse and keyboard events using pynput
and converts them into a list of Action objects.
"""

import logging
import threading
import time
from typing import Any, Optional

from pynput import mouse as pmouse, keyboard as pkeyboard

from core.action import Action, DelayAction, get_action_class

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependency – modules register actions on import
_modules_loaded = False


def _ensure_modules() -> None:
    global _modules_loaded
    if not _modules_loaded:
        import modules.mouse    # noqa: F401  registers mouse actions
        import modules.keyboard  # noqa: F401  registers keyboard actions
        _modules_loaded = True


class Recorder:
    """
    Records mouse clicks and keyboard presses into a list of Actions.

    Usage
    -----
    recorder = Recorder()
    recorder.start()          # begins listening
    # ... user performs actions ...
    actions = recorder.stop()  # returns list[Action]
    """

    def __init__(self, record_mouse: bool = True,
                 record_keyboard: bool = True,
                 min_delay_ms: int = 50,
                 capture_context: bool = False,
                 macro_dir: str = "macros") -> None:
        _ensure_modules()
        self._record_mouse = record_mouse
        self._record_keyboard = record_keyboard
        self._min_delay_ms = min_delay_ms
        self._capture_context = capture_context
        self._macro_dir = macro_dir

        self._actions: list[Action] = []
        self._actions_lock = threading.Lock()
        self._last_time: float = 0.0
        self._is_recording = False

        self._mouse_listener: Optional[pmouse.Listener] = None
        self._keyboard_listener: Optional[pkeyboard.Listener] = None

        # Buffer for grouping consecutive key presses into TypeText
        self._key_buffer: list[str] = []
        self._key_buffer_time: float = 0.0

    # -- public API ----------------------------------------------------------
    def start(self) -> None:
        """Start recording."""
        self._actions.clear()
        self._key_buffer.clear()
        self._last_time = time.perf_counter()
        self._is_recording = True

        if self._record_mouse:
            self._mouse_listener = pmouse.Listener(
                on_click=self._on_click,
                on_scroll=self._on_scroll,
            )
            self._mouse_listener.start()

        if self._record_keyboard:
            self._keyboard_listener = pkeyboard.Listener(
                on_press=self._on_key_press,
            )
            self._keyboard_listener.start()

        logger.info("Recording started (mouse=%s, keyboard=%s)",
                    self._record_mouse, self._record_keyboard)

    def stop(self) -> list[Action]:
        """Stop recording and return the captured actions."""
        self._is_recording = False
        self._flush_key_buffer()

        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None

        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

        logger.info("Recording stopped – captured %d actions",
                    len(self._actions))
        return list(self._actions)

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def action_count(self) -> int:
        with self._actions_lock:
            return len(self._actions)

    def get_actions_snapshot(self, start: int = 0) -> list[Action]:
        """Return a thread-safe copy of recorded actions from index `start`."""
        with self._actions_lock:
            return list(self._actions[start:])

    # -- delay helper --------------------------------------------------------
    def _record_delay(self) -> None:
        """Insert a DelayAction for the time elapsed since the last event."""
        now = time.perf_counter()
        elapsed_ms = int((now - self._last_time) * 1000)
        if elapsed_ms >= self._min_delay_ms:
            with self._actions_lock:
                self._actions.append(DelayAction(duration_ms=elapsed_ms))
        self._last_time = now

    def _capture_click_context(self, x: int, y: int,
                                size: int = 80) -> str | None:
        """Capture a small screenshot around click point as visual context."""
        if not self._capture_context:
            return None
        try:
            import pyautogui
            from pathlib import Path as _Path
            half = size // 2
            sx = max(0, x - half)
            sy = max(0, y - half)
            screenshot = pyautogui.screenshot(region=(sx, sy, size, size))
            ctx_dir = _Path(self._macro_dir) / "contexts"
            ctx_dir.mkdir(parents=True, exist_ok=True)
            filename = f"ctx_{int(time.time() * 1000)}.png"
            path = ctx_dir / filename
            screenshot.save(str(path))
            return str(path)
        except (OSError, TypeError, ValueError):
            logger.debug("Context capture failed, using coordinate only")
            return None

    # -- mouse callbacks -----------------------------------------------------
    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        if not self._is_recording or not pressed:
            return
        self._flush_key_buffer()
        self._record_delay()

        btn = "left" if button == pmouse.Button.left else \
              "right" if button == pmouse.Button.right else "middle"

        action_type = "mouse_click" if btn == "left" else \
                      "mouse_right_click" if btn == "right" else "mouse_click"
        try:
            ctx_path = self._capture_click_context(int(x), int(y))
            cls = get_action_class(action_type)
            action = cls(x=int(x), y=int(y),
                         context_image=ctx_path or "")  # type: ignore[call-arg]
            with self._actions_lock:
                self._actions.append(action)
            logger.debug("Recorded %s at (%d, %d)%s", action_type, x, y,
                         f" [ctx: {ctx_path}]" if ctx_path else "")
        except (TypeError, ValueError, KeyError) as exc:
            logger.warning("Failed to record %s: %s", action_type, exc)

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if not self._is_recording:
            return
        self._flush_key_buffer()
        self._record_delay()

        try:
            cls = get_action_class("mouse_scroll")
            action = cls(x=int(x), y=int(y), clicks=int(dy))  # type: ignore[call-arg]
            with self._actions_lock:
                self._actions.append(action)
        except (TypeError, ValueError, KeyError):
            logger.warning("Failed to record scroll", exc_info=True)

    # -- keyboard callbacks --------------------------------------------------
    def _on_key_press(self, key: Any) -> None:
        if not self._is_recording:
            return

        # Check if it's a printable character
        try:
            char = key.char
            if char is not None:
                if not self._key_buffer:
                    self._record_delay()
                self._key_buffer.append(char)
                self._key_buffer_time = time.perf_counter()
                return
        except AttributeError:
            pass

        # Special key – flush buffer first, then record key press
        self._flush_key_buffer()
        self._record_delay()

        key_name = key.name if hasattr(key, "name") else str(key)
        try:
            cls = get_action_class("key_press")
            action = cls(key=key_name)  # type: ignore[call-arg]
            with self._actions_lock:
                self._actions.append(action)
            logger.debug("Recorded key_press: %s", key_name)
        except (TypeError, ValueError, KeyError):
            logger.warning("Failed to record key: %s", key_name, exc_info=True)

    def _flush_key_buffer(self) -> None:
        """Convert buffered characters into a TypeText action."""
        if not self._key_buffer:
            return
        text = "".join(self._key_buffer)
        self._key_buffer.clear()

        try:
            cls = get_action_class("type_text")
            action = cls(text=text)  # type: ignore[call-arg]
            with self._actions_lock:
                self._actions.append(action)
            logger.debug("Recorded type_text: '%s'", text)
        except ValueError:
            pass
