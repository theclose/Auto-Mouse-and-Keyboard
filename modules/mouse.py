"""
Mouse automation actions.
Provides click, double-click, right-click, move, drag, and scroll.
"""

import logging
from typing import Any

from core.action import Action, register_action

logger = logging.getLogger(__name__)

# Lazy-load pyautogui to save ~680ms startup
_pyautogui = None


def _pag():
    """Return pyautogui module, importing on first call."""
    global _pyautogui
    if _pyautogui is None:
        import pyautogui

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.005  # 5ms — minimal safe pause
        _pyautogui = pyautogui
    return _pyautogui


import os


def _resolve_visual(context_image: str, fallback_x: int, fallback_y: int) -> tuple[int, int]:
    """Try to find context image on screen; return match center or fallback."""
    if not context_image:
        return fallback_x, fallback_y
    if not os.path.isfile(context_image):
        return fallback_x, fallback_y
    try:
        from modules.image import get_image_finder

        finder = get_image_finder()
        bbox = finder.find_on_screen(context_image, confidence=0.80, timeout_ms=500, grayscale=True)
        if bbox:
            cx, cy = bbox[0] + bbox[2] // 2, bbox[1] + bbox[3] // 2
            logger.debug("Visual match at (%d, %d) for %s", cx, cy, context_image)
            return cx, cy
    except Exception:
        logger.debug("Visual context lookup failed, using coordinates")
    return fallback_x, fallback_y


@register_action("mouse_click")
class MouseClick(Action):
    """Left-click at (x, y) with optional visual context fallback."""

    __slots__ = ('x', 'y', 'duration', 'context_image', '_dynamic_x', '_dynamic_y')

    def __init__(self, x: int = 0, y: int = 0, duration: float = 0.0, context_image: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.duration = duration
        self.context_image = context_image
        self._dynamic_x: str = ""
        self._dynamic_y: str = ""

    def _resolve_coords(self) -> tuple[int, int]:
        """Resolve coordinates, using ${var} if set."""
        rx, ry = self.x, self.y
        if self._dynamic_x or self._dynamic_y:
            from core.engine_context import get_context

            ctx = get_context()
            if ctx:
                if self._dynamic_x:
                    try:
                        rx = int(float(ctx.interpolate(self._dynamic_x)))
                    except (ValueError, TypeError):
                        pass
                if self._dynamic_y:
                    try:
                        ry = int(float(ctx.interpolate(self._dynamic_y)))
                    except (ValueError, TypeError):
                        pass
        return rx, ry

    def execute(self) -> bool:
        rx, ry = self._resolve_coords()
        tx, ty = _resolve_visual(self.context_image, rx, ry)
        _pag().click(tx, ty, duration=self.duration)
        logger.debug("Clicked at (%d, %d)", tx, ty)
        return True

    def _get_params(self) -> dict[str, Any]:
        d: dict[str, Any] = {"x": self.x, "y": self.y, "duration": self.duration}
        if self.context_image:
            d["context_image"] = self.context_image
        if self._dynamic_x:
            d["dynamic_x"] = self._dynamic_x
        if self._dynamic_y:
            d["dynamic_y"] = self._dynamic_y
        return d

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.duration = params.get("duration", 0.0)
        self.context_image = params.get("context_image", "")
        self._dynamic_x = params.get("dynamic_x", "")
        self._dynamic_y = params.get("dynamic_y", "")

    def get_display_name(self) -> str:
        suffix = " 📷" if self.context_image else ""
        if self._dynamic_x or self._dynamic_y:
            return f"Click ({self._dynamic_x or self.x}, {self._dynamic_y or self.y}){suffix}"
        return f"Click ({self.x}, {self.y}){suffix}"


@register_action("mouse_double_click")
class MouseDoubleClick(Action):
    """Double-click at (x, y) with optional visual context fallback."""

    __slots__ = ('x', 'y', 'context_image', '_dynamic_x', '_dynamic_y')

    def __init__(self, x: int = 0, y: int = 0, context_image: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.context_image = context_image
        self._dynamic_x: str = ""
        self._dynamic_y: str = ""

    def _resolve_coords(self) -> tuple[int, int]:
        """Resolve coordinates, using ${var} if set."""
        rx, ry = self.x, self.y
        if self._dynamic_x or self._dynamic_y:
            from core.engine_context import get_context

            ctx = get_context()
            if ctx:
                if self._dynamic_x:
                    try:
                        rx = int(float(ctx.interpolate(self._dynamic_x)))
                    except (ValueError, TypeError):
                        pass
                if self._dynamic_y:
                    try:
                        ry = int(float(ctx.interpolate(self._dynamic_y)))
                    except (ValueError, TypeError):
                        pass
        return rx, ry

    def execute(self) -> bool:
        rx, ry = self._resolve_coords()
        tx, ty = _resolve_visual(self.context_image, rx, ry)
        _pag().doubleClick(tx, ty)
        logger.debug("Double-clicked at (%d, %d)", tx, ty)
        return True

    def _get_params(self) -> dict[str, Any]:
        d: dict[str, Any] = {"x": self.x, "y": self.y}
        if self.context_image:
            d["context_image"] = self.context_image
        if self._dynamic_x:
            d["dynamic_x"] = self._dynamic_x
        if self._dynamic_y:
            d["dynamic_y"] = self._dynamic_y
        return d

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.context_image = params.get("context_image", "")
        self._dynamic_x = params.get("dynamic_x", "")
        self._dynamic_y = params.get("dynamic_y", "")

    def get_display_name(self) -> str:
        suffix = " 📷" if self.context_image else ""
        if self._dynamic_x or self._dynamic_y:
            return f"Double Click ({self._dynamic_x or self.x}, {self._dynamic_y or self.y}){suffix}"
        return f"Double Click ({self.x}, {self.y}){suffix}"


@register_action("mouse_right_click")
class MouseRightClick(Action):
    """Right-click at (x, y) with optional visual context fallback."""

    __slots__ = ('x', 'y', 'context_image', '_dynamic_x', '_dynamic_y')

    def __init__(self, x: int = 0, y: int = 0, context_image: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.context_image = context_image
        self._dynamic_x: str = ""
        self._dynamic_y: str = ""

    def _resolve_coords(self) -> tuple[int, int]:
        """Resolve coordinates, using ${var} if set."""
        rx, ry = self.x, self.y
        if self._dynamic_x or self._dynamic_y:
            from core.engine_context import get_context

            ctx = get_context()
            if ctx:
                if self._dynamic_x:
                    try:
                        rx = int(float(ctx.interpolate(self._dynamic_x)))
                    except (ValueError, TypeError):
                        pass
                if self._dynamic_y:
                    try:
                        ry = int(float(ctx.interpolate(self._dynamic_y)))
                    except (ValueError, TypeError):
                        pass
        return rx, ry

    def execute(self) -> bool:
        rx, ry = self._resolve_coords()
        tx, ty = _resolve_visual(self.context_image, rx, ry)
        _pag().rightClick(tx, ty)
        logger.debug("Right-clicked at (%d, %d)", tx, ty)
        return True

    def _get_params(self) -> dict[str, Any]:
        d: dict[str, Any] = {"x": self.x, "y": self.y}
        if self.context_image:
            d["context_image"] = self.context_image
        if self._dynamic_x:
            d["dynamic_x"] = self._dynamic_x
        if self._dynamic_y:
            d["dynamic_y"] = self._dynamic_y
        return d

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.context_image = params.get("context_image", "")
        self._dynamic_x = params.get("dynamic_x", "")
        self._dynamic_y = params.get("dynamic_y", "")

    def get_display_name(self) -> str:
        suffix = " 📷" if self.context_image else ""
        if self._dynamic_x or self._dynamic_y:
            return f"Right Click ({self._dynamic_x or self.x}, {self._dynamic_y or self.y}){suffix}"
        return f"Right Click ({self.x}, {self.y}){suffix}"


@register_action("mouse_move")
class MouseMove(Action):
    """Move the cursor to (x, y). Supports ${var} in coordinates."""

    __slots__ = ('x', 'y', 'duration', '_dynamic_x', '_dynamic_y')

    def __init__(self, x: int = 0, y: int = 0, duration: float = 0.25, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.duration = duration
        self._dynamic_x: str = ""
        self._dynamic_y: str = ""

    def _resolve_coords(self) -> tuple[int, int]:
        """Resolve coordinates, using ${var} if set."""
        rx, ry = self.x, self.y
        if self._dynamic_x or self._dynamic_y:
            from core.engine_context import get_context

            ctx = get_context()
            if ctx:
                if self._dynamic_x:
                    try:
                        rx = int(float(ctx.interpolate(self._dynamic_x)))
                    except (ValueError, TypeError):
                        pass
                if self._dynamic_y:
                    try:
                        ry = int(float(ctx.interpolate(self._dynamic_y)))
                    except (ValueError, TypeError):
                        pass
        return rx, ry

    def execute(self) -> bool:
        rx, ry = self._resolve_coords()
        _pag().moveTo(rx, ry, duration=self.duration)
        return True

    def _get_params(self) -> dict[str, Any]:
        p: dict[str, Any] = {"x": self.x, "y": self.y, "duration": self.duration}
        if self._dynamic_x:
            p["dynamic_x"] = self._dynamic_x
        if self._dynamic_y:
            p["dynamic_y"] = self._dynamic_y
        return p

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.duration = params.get("duration", 0.25)
        self._dynamic_x = params.get("dynamic_x", "")
        self._dynamic_y = params.get("dynamic_y", "")

    def get_display_name(self) -> str:
        if self._dynamic_x or self._dynamic_y:
            return f"Move to ({self._dynamic_x or self.x}, {self._dynamic_y or self.y})"
        return f"Move to ({self.x}, {self.y})"


@register_action("mouse_drag")
class MouseDrag(Action):
    """Drag from current position to (x, y). Supports ${var} in coordinates."""

    __slots__ = ('x', 'y', 'start_x', 'start_y', 'duration', 'button', '_dynamic_x', '_dynamic_y')

    def __init__(self, x: int = 0, y: int = 0, duration: float = 0.5, button: str = "left",
                 start_x: int = 0, start_y: int = 0, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.start_x = start_x
        self.start_y = start_y
        self.duration = duration
        self.button = button
        self._dynamic_x: str = ""
        self._dynamic_y: str = ""

    def _resolve_coords(self) -> tuple[int, int]:
        rx, ry = self.x, self.y
        if self._dynamic_x or self._dynamic_y:
            from core.engine_context import get_context

            ctx = get_context()
            if ctx:
                if self._dynamic_x:
                    try:
                        rx = int(float(ctx.interpolate(self._dynamic_x)))
                    except (ValueError, TypeError):
                        pass
                if self._dynamic_y:
                    try:
                        ry = int(float(ctx.interpolate(self._dynamic_y)))
                    except (ValueError, TypeError):
                        pass
        return rx, ry

    def execute(self) -> bool:
        rx, ry = self._resolve_coords()
        # Move to start position first if specified
        if self.start_x or self.start_y:
            _pag().moveTo(self.start_x, self.start_y, duration=0.05)
        _pag().dragTo(rx, ry, duration=self.duration, button=self.button)
        return True

    def _get_params(self) -> dict[str, Any]:
        p: dict[str, Any] = {"x": self.x, "y": self.y, "duration": self.duration, "button": self.button}
        if self.start_x or self.start_y:
            p["start_x"] = self.start_x
            p["start_y"] = self.start_y
        if self._dynamic_x:
            p["dynamic_x"] = self._dynamic_x
        if self._dynamic_y:
            p["dynamic_y"] = self._dynamic_y
        return p

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.start_x = params.get("start_x", 0)
        self.start_y = params.get("start_y", 0)
        self.duration = params.get("duration", 0.5)
        self.button = params.get("button", "left")
        self._dynamic_x = params.get("dynamic_x", "")
        self._dynamic_y = params.get("dynamic_y", "")

    def get_display_name(self) -> str:
        start = f"({self.start_x}, {self.start_y}) " if (self.start_x or self.start_y) else ""
        if self._dynamic_x or self._dynamic_y:
            return f"Drag {start}to ({self._dynamic_x or self.x}, {self._dynamic_y or self.y})"
        return f"Drag {start}to ({self.x}, {self.y})"


@register_action("mouse_scroll")
class MouseScroll(Action):
    """Scroll the mouse wheel."""

    __slots__ = ('x', 'y', 'clicks')

    def __init__(self, x: int = 0, y: int = 0, clicks: int = 3, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.clicks = clicks  # positive = up, negative = down

    def execute(self) -> bool:
        if self.clicks == 0:
            logger.debug("MouseScroll: clicks=0 — skipping")
            return True
        _pag().scroll(self.clicks, self.x, self.y)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "clicks": self.clicks}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.clicks = params.get("clicks", 3)

    def get_display_name(self) -> str:
        direction = "up" if self.clicks > 0 else "down"
        return f"Scroll {direction} {abs(self.clicks)} clicks"


# ══════════════════════════════════════════════════════════════
#  STEALTH ACTIONS — PostMessage-based (non-invasive)
#  Physical mouse/keyboard are NEVER hijacked.
# ══════════════════════════════════════════════════════════════


@register_action("stealth_click")
class StealthClick(Action):
    """Click a window via PostMessage — does NOT move the physical cursor.

    Sends MOUSEMOVE → LBUTTONDOWN → (humanized delay) → LBUTTONUP
    directly to the target window's message queue. Works on hidden,
    minimized, or occluded windows.

    Limitations:
    - Does not work with DirectX/OpenGL fullscreen apps.
    - Coordinates are client-relative (relative to window's top-left).
    """

    __slots__ = ('x', 'y', 'window_title', 'right_click', 'double_click')

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        window_title: str = "",
        right_click: bool = False,
        double_click: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.window_title = window_title
        self.right_click = right_click
        self.double_click = double_click

    def execute(self) -> bool:
        from core.win32_stealth import (
            find_window_by_title,
            stealth_click,
            stealth_double_click,
        )

        if not self.window_title:
            logger.error("StealthClick: no window_title specified")
            return False

        hwnd = find_window_by_title(self.window_title)
        if not hwnd:
            logger.error("StealthClick: window not found: '%s'", self.window_title)
            return False

        if self.double_click:
            stealth_double_click(hwnd, self.x, self.y)
        else:
            stealth_click(hwnd, self.x, self.y, right=self.right_click)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "window_title": self.window_title,
            "right_click": self.right_click,
            "double_click": self.double_click,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.window_title = params.get("window_title", "")
        self.right_click = params.get("right_click", False)
        self.double_click = params.get("double_click", False)

    def get_display_name(self) -> str:
        btn = "Double" if self.double_click else ("Right" if self.right_click else "Left")
        win = self.window_title[:20] + "…" if len(self.window_title) > 20 else self.window_title
        return f"👻 Stealth {btn} Click ({self.x}, {self.y}) → {win}"


@register_action("stealth_type")
class StealthType(Action):
    """Type text into a window via WM_CHAR — does NOT use the physical keyboard.

    Each character is sent as a WM_CHAR message directly to the target
    window's message queue. Works on hidden or background windows.
    """

    __slots__ = ('text', 'window_title', 'key_delay_ms')

    def __init__(
        self,
        text: str = "",
        window_title: str = "",
        key_delay_ms: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.text = text
        self.window_title = window_title
        self.key_delay_ms = key_delay_ms

    def execute(self) -> bool:
        from core.win32_stealth import find_window_by_title, stealth_type_text

        if not self.window_title:
            logger.error("StealthType: no window_title specified")
            return False

        hwnd = find_window_by_title(self.window_title)
        if not hwnd:
            logger.error("StealthType: window not found: '%s'", self.window_title)
            return False

        stealth_type_text(hwnd, self.text, delay_ms=self.key_delay_ms)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "window_title": self.window_title,
            "key_delay_ms": self.key_delay_ms,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.text = params.get("text", "")
        self.window_title = params.get("window_title", "")
        self.key_delay_ms = params.get("key_delay_ms", 0)

    def get_display_name(self) -> str:
        preview = self.text[:25] + "…" if len(self.text) > 25 else self.text
        win = self.window_title[:20] + "…" if len(self.window_title) > 20 else self.window_title
        return f"👻 Stealth Type \"{preview}\" → {win}"
