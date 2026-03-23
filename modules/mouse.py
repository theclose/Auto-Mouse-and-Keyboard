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


def _resolve_visual(context_image: str, fallback_x: int,
                    fallback_y: int) -> tuple[int, int]:
    """Try to find context image on screen; return match center or fallback."""
    if not context_image:
        return fallback_x, fallback_y
    if not os.path.isfile(context_image):
        return fallback_x, fallback_y
    try:
        from modules.image import get_image_finder
        finder = get_image_finder()
        bbox = finder.find_on_screen(context_image, confidence=0.80,
                                      timeout_ms=500, grayscale=True)
        if bbox:
            cx, cy = bbox[0] + bbox[2] // 2, bbox[1] + bbox[3] // 2
            logger.debug("Visual match at (%d, %d) for %s",
                         cx, cy, context_image)
            return cx, cy
    except Exception:
        logger.debug("Visual context lookup failed, using coordinates")
    return fallback_x, fallback_y


@register_action("mouse_click")
class MouseClick(Action):
    """Left-click at (x, y) with optional visual context fallback."""

    def __init__(self, x: int = 0, y: int = 0, duration: float = 0.0,
                 context_image: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.duration = duration
        self.context_image = context_image

    def execute(self) -> bool:
        tx, ty = _resolve_visual(self.context_image, self.x, self.y)
        _pag().click(tx, ty, duration=self.duration)
        logger.debug("Clicked at (%d, %d)", tx, ty)
        return True

    def _get_params(self) -> dict[str, Any]:
        d: dict[str, Any] = {"x": self.x, "y": self.y,
                              "duration": self.duration}
        if self.context_image:
            d["context_image"] = self.context_image
        return d

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.duration = params.get("duration", 0.0)
        self.context_image = params.get("context_image", "")

    def get_display_name(self) -> str:
        suffix = " 📷" if self.context_image else ""
        return f"Click ({self.x}, {self.y}){suffix}"


@register_action("mouse_double_click")
class MouseDoubleClick(Action):
    """Double-click at (x, y) with optional visual context fallback."""

    def __init__(self, x: int = 0, y: int = 0,
                 context_image: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.context_image = context_image

    def execute(self) -> bool:
        tx, ty = _resolve_visual(self.context_image, self.x, self.y)
        _pag().doubleClick(tx, ty)
        logger.debug("Double-clicked at (%d, %d)", tx, ty)
        return True

    def _get_params(self) -> dict[str, Any]:
        d: dict[str, Any] = {"x": self.x, "y": self.y}
        if self.context_image:
            d["context_image"] = self.context_image
        return d

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.context_image = params.get("context_image", "")

    def get_display_name(self) -> str:
        suffix = " 📷" if self.context_image else ""
        return f"Double Click ({self.x}, {self.y}){suffix}"


@register_action("mouse_right_click")
class MouseRightClick(Action):
    """Right-click at (x, y) with optional visual context fallback."""

    def __init__(self, x: int = 0, y: int = 0,
                 context_image: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.context_image = context_image

    def execute(self) -> bool:
        tx, ty = _resolve_visual(self.context_image, self.x, self.y)
        _pag().rightClick(tx, ty)
        logger.debug("Right-clicked at (%d, %d)", tx, ty)
        return True

    def _get_params(self) -> dict[str, Any]:
        d: dict[str, Any] = {"x": self.x, "y": self.y}
        if self.context_image:
            d["context_image"] = self.context_image
        return d

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.context_image = params.get("context_image", "")

    def get_display_name(self) -> str:
        suffix = " 📷" if self.context_image else ""
        return f"Right Click ({self.x}, {self.y}){suffix}"


@register_action("mouse_move")
class MouseMove(Action):
    """Move the cursor to (x, y). Supports ${var} in coordinates."""

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
                    try: rx = int(float(ctx.interpolate(self._dynamic_x)))
                    except (ValueError, TypeError): pass
                if self._dynamic_y:
                    try: ry = int(float(ctx.interpolate(self._dynamic_y)))
                    except (ValueError, TypeError): pass
        return rx, ry

    def execute(self) -> bool:
        rx, ry = self._resolve_coords()
        _pag().moveTo(rx, ry, duration=self.duration)
        return True

    def _get_params(self) -> dict[str, Any]:
        p: dict[str, Any] = {"x": self.x, "y": self.y, "duration": self.duration}
        if self._dynamic_x: p["dynamic_x"] = self._dynamic_x
        if self._dynamic_y: p["dynamic_y"] = self._dynamic_y
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

    def __init__(self, x: int = 0, y: int = 0,
                 duration: float = 0.5, button: str = "left", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
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
                    try: rx = int(float(ctx.interpolate(self._dynamic_x)))
                    except (ValueError, TypeError): pass
                if self._dynamic_y:
                    try: ry = int(float(ctx.interpolate(self._dynamic_y)))
                    except (ValueError, TypeError): pass
        return rx, ry

    def execute(self) -> bool:
        rx, ry = self._resolve_coords()
        _pag().dragTo(rx, ry, duration=self.duration, button=self.button)
        return True

    def _get_params(self) -> dict[str, Any]:
        p: dict[str, Any] = {"x": self.x, "y": self.y,
             "duration": self.duration, "button": self.button}
        if self._dynamic_x: p["dynamic_x"] = self._dynamic_x
        if self._dynamic_y: p["dynamic_y"] = self._dynamic_y
        return p

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.duration = params.get("duration", 0.5)
        self.button = params.get("button", "left")
        self._dynamic_x = params.get("dynamic_x", "")
        self._dynamic_y = params.get("dynamic_y", "")

    def get_display_name(self) -> str:
        if self._dynamic_x or self._dynamic_y:
            return f"Drag to ({self._dynamic_x or self.x}, {self._dynamic_y or self.y})"
        return f"Drag to ({self.x}, {self.y})"


@register_action("mouse_scroll")
class MouseScroll(Action):
    """Scroll the mouse wheel."""

    def __init__(self, x: int = 0, y: int = 0, clicks: int = 3, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.clicks = clicks  # positive = up, negative = down

    def execute(self) -> bool:
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
