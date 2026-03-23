"""
Recorder – captures live mouse and keyboard events using pynput
and converts them into a list of Action objects.

v2.9: double-click detection, key combo detection, mouse drag,
      pause/resume support.
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


# Modifier keys that form combos (Ctrl+C, Alt+Tab, etc.)
_MODIFIER_KEYS = {
    pkeyboard.Key.ctrl, pkeyboard.Key.ctrl_l, pkeyboard.Key.ctrl_r,
    pkeyboard.Key.alt, pkeyboard.Key.alt_l, pkeyboard.Key.alt_r,
    pkeyboard.Key.shift, pkeyboard.Key.shift_l, pkeyboard.Key.shift_r,
    pkeyboard.Key.cmd, pkeyboard.Key.cmd_l, pkeyboard.Key.cmd_r,
}

# Canonical names for modifier display
_MOD_NAMES = {
    pkeyboard.Key.ctrl: "ctrl", pkeyboard.Key.ctrl_l: "ctrl",
    pkeyboard.Key.ctrl_r: "ctrl",
    pkeyboard.Key.alt: "alt", pkeyboard.Key.alt_l: "alt",
    pkeyboard.Key.alt_r: "alt",
    pkeyboard.Key.shift: "shift", pkeyboard.Key.shift_l: "shift",
    pkeyboard.Key.shift_r: "shift",
    pkeyboard.Key.cmd: "win", pkeyboard.Key.cmd_l: "win",
    pkeyboard.Key.cmd_r: "win",
}


class Recorder:
    """
    Records mouse clicks and keyboard presses into a list of Actions.

    Features:
    - Double-click detection (2 clicks <300ms at same position)
    - Key combo detection (Ctrl+C, Alt+Tab, etc.)
    - Mouse drag detection (press→move→release)
    - Pause/resume support
    - Optional context image capture
    """

    # double-click detection threshold
    DOUBLE_CLICK_MS = 300
    DOUBLE_CLICK_PX = 10   # max distance between 2 clicks

    # drag detection threshold
    DRAG_MIN_PX = 8        # min distance for drag vs click

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
        self._is_paused = False

        self._mouse_listener: Optional[pmouse.Listener] = None
        self._keyboard_listener: Optional[pkeyboard.Listener] = None

        # Buffer for grouping consecutive key presses into TypeText
        self._key_buffer: list[str] = []
        self._key_buffer_time: float = 0.0

        # Double-click detection state
        self._last_click_time: float = 0.0
        self._last_click_pos: tuple[int, int] = (0, 0)
        self._last_click_button: str = ""

        # Modifier tracking for key combos (#3)
        self._active_modifiers: set = set()

        # Drag detection state (#6)
        self._mouse_pressed: bool = False
        self._press_pos: tuple[int, int] = (0, 0)
        self._press_button: str = "left"

    # -- public API ----------------------------------------------------------
    def start(self) -> None:
        """Start recording."""
        self._actions.clear()
        self._key_buffer.clear()
        self._active_modifiers.clear()
        self._last_time = time.perf_counter()
        self._is_recording = True
        self._is_paused = False

        if self._record_mouse:
            self._mouse_listener = pmouse.Listener(
                on_click=self._on_click,
                on_scroll=self._on_scroll,
            )
            self._mouse_listener.start()

        if self._record_keyboard:
            self._keyboard_listener = pkeyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._keyboard_listener.start()

        logger.info("Recording started (mouse=%s, keyboard=%s)",
                    self._record_mouse, self._record_keyboard)

    def stop(self) -> list[Action]:
        """Stop recording and return the captured actions."""
        self._is_recording = False
        self._is_paused = False
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

    def pause(self) -> None:
        """Pause recording — events are silently ignored."""
        if self._is_recording and not self._is_paused:
            self._is_paused = True
            self._flush_key_buffer()
            logger.info("Recording paused")

    def resume(self) -> None:
        """Resume recording after pause."""
        if self._is_recording and self._is_paused:
            self._is_paused = False
            self._last_time = time.perf_counter()  # reset delay baseline
            logger.info("Recording resumed")

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def is_paused(self) -> bool:
        return self._is_paused

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
        if not self._is_recording or self._is_paused:
            return

        btn = ("left" if button == pmouse.Button.left else
               "right" if button == pmouse.Button.right else "middle")

        if pressed:
            # Track press for drag detection (#6)
            self._mouse_pressed = True
            self._press_pos = (int(x), int(y))
            self._press_button = btn
            return  # don't record click yet — wait for release

        # === RELEASE ===
        self._mouse_pressed = False
        rx, ry = int(x), int(y)
        px, py = self._press_pos

        # Drag detection (#6): if moved >DRAG_MIN_PX, record as drag
        dist = ((rx - px) ** 2 + (ry - py) ** 2) ** 0.5
        if dist > self.DRAG_MIN_PX:
            self._flush_key_buffer()
            self._record_delay()
            try:
                cls = get_action_class("mouse_drag")
                action = cls(x=rx, y=ry, duration=0.5,
                             button=btn)  # type: ignore[call-arg]
                with self._actions_lock:
                    self._actions.append(action)
                logger.debug("Recorded drag to (%d, %d)", rx, ry)
            except (TypeError, ValueError, KeyError) as exc:
                logger.warning("Failed to record drag: %s", exc)
            self._last_click_time = 0  # reset double-click
            return

        # Click recording with double-click detection (#2)
        self._flush_key_buffer()
        self._record_delay()

        now = time.perf_counter()
        elapsed = (now - self._last_click_time) * 1000
        click_dist = ((rx - self._last_click_pos[0]) ** 2 +
                      (ry - self._last_click_pos[1]) ** 2) ** 0.5

        if (btn == "left" and
                btn == self._last_click_button and
                elapsed < self.DOUBLE_CLICK_MS and
                click_dist < self.DOUBLE_CLICK_PX):
            # Double-click detected! Replace last click with double-click
            with self._actions_lock:
                # Remove previous click action (it was a single click)
                if self._actions and hasattr(self._actions[-1], 'ACTION_TYPE'):
                    if self._actions[-1].ACTION_TYPE == "mouse_click":
                        self._actions.pop()
                        # Also remove its delay if present
                        if (self._actions and
                                isinstance(self._actions[-1], DelayAction)):
                            self._actions.pop()
            try:
                ctx_path = self._capture_click_context(rx, ry)
                cls = get_action_class("mouse_double_click")
                action = cls(x=rx, y=ry,
                             context_image=ctx_path or "")  # type: ignore
                with self._actions_lock:
                    self._actions.append(action)
                logger.debug("Recorded double_click at (%d, %d)", rx, ry)
            except (TypeError, ValueError, KeyError) as exc:
                logger.warning("Failed to record double_click: %s", exc)
            self._last_click_time = 0  # reset
            return

        # Regular single click
        action_type = ("mouse_click" if btn == "left" else
                       "mouse_right_click" if btn == "right" else
                       "mouse_click")
        try:
            ctx_path = self._capture_click_context(rx, ry)
            cls = get_action_class(action_type)
            action = cls(x=rx, y=ry,
                         context_image=ctx_path or "")  # type: ignore[call-arg]
            with self._actions_lock:
                self._actions.append(action)
            logger.debug("Recorded %s at (%d, %d)", action_type, rx, ry)
        except (TypeError, ValueError, KeyError) as exc:
            logger.warning("Failed to record %s: %s", action_type, exc)

        self._last_click_time = now
        self._last_click_pos = (rx, ry)
        self._last_click_button = btn

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if not self._is_recording or self._is_paused:
            return
        self._flush_key_buffer()
        self._record_delay()

        try:
            cls = get_action_class("mouse_scroll")
            action = cls(x=int(x), y=int(y),
                         clicks=int(dy))  # type: ignore[call-arg]
            with self._actions_lock:
                self._actions.append(action)
        except (TypeError, ValueError, KeyError):
            logger.warning("Failed to record scroll", exc_info=True)

    # -- keyboard callbacks --------------------------------------------------
    def _on_key_press(self, key: Any) -> None:
        if not self._is_recording or self._is_paused:
            return

        # Track modifiers (#3)
        if key in _MODIFIER_KEYS:
            self._active_modifiers.add(key)
            return  # Don't record modifier press alone

        # Check if modifier is held → key combo (#3)
        if self._active_modifiers:
            self._flush_key_buffer()
            self._record_delay()
            self._record_key_combo(key)
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
            logger.warning("Failed to record key: %s", key_name,
                           exc_info=True)

    def _on_key_release(self, key: Any) -> None:
        """Track modifier release for combo detection (#3)."""
        if key in _MODIFIER_KEYS:
            self._active_modifiers.discard(key)

    def _record_key_combo(self, key: Any) -> None:
        """Record a key combo like Ctrl+C, Alt+Tab (#3)."""
        # Build combo string: "ctrl+c", "alt+tab", "ctrl+shift+s"
        mod_names = sorted(set(
            _MOD_NAMES.get(m, str(m)) for m in self._active_modifiers
        ))

        # Get the key name
        try:
            key_name = key.char if key.char else key.name
        except AttributeError:
            key_name = key.name if hasattr(key, "name") else str(key)

        combo = "+".join(mod_names + [key_name])

        try:
            cls = get_action_class("key_combo")
            action = cls(keys=combo)  # type: ignore[call-arg]
            with self._actions_lock:
                self._actions.append(action)
            logger.debug("Recorded key_combo: %s", combo)
        except (TypeError, ValueError, KeyError) as exc:
            # Fallback to hotkey if key_combo fails
            try:
                cls = get_action_class("hotkey")
                action = cls(keys=combo)  # type: ignore[call-arg]
                with self._actions_lock:
                    self._actions.append(action)
                logger.debug("Recorded hotkey: %s", combo)
            except (TypeError, ValueError, KeyError):
                logger.warning("Failed to record combo: %s (%s)", combo, exc)

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
