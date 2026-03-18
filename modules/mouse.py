"""
Mouse automation actions.
Provides click, double-click, right-click, move, drag, and scroll.
"""

import logging
import pyautogui
from typing import Any

from core.action import Action, register_action

logger = logging.getLogger(__name__)

# Safety: pyautogui fail-safe (move mouse to top-left corner to abort)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.03  # small default pause between pyautogui calls

import os


def _resolve_visual(context_image: str, fallback_x: int,
                    fallback_y: int) -> tuple[int, int]:
    """Try to find context image on screen; return match center or fallback."""
    if not context_image or not os.path.isfile(context_image):
        return fallback_x, fallback_y
    try:
        from modules.image import ImageFinder
        result = ImageFinder.find(context_image, confidence=0.80, timeout=0.5)
        if result:
            logger.debug("Visual match at (%d, %d) for %s",
                         result[0], result[1], context_image)
            return result[0], result[1]
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
        pyautogui.click(tx, ty, duration=self.duration)
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
        pyautogui.doubleClick(tx, ty)
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
        pyautogui.rightClick(tx, ty)
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
    """Move the cursor to (x, y)."""

    def __init__(self, x: int = 0, y: int = 0, duration: float = 0.25, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.duration = duration

    def execute(self) -> bool:
        pyautogui.moveTo(self.x, self.y, duration=self.duration)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "duration": self.duration}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.duration = params.get("duration", 0.25)

    def get_display_name(self) -> str:
        return f"Move to ({self.x}, {self.y})"


@register_action("mouse_drag")
class MouseDrag(Action):
    """Drag from current position to (x, y)."""

    def __init__(self, x: int = 0, y: int = 0,
                 duration: float = 0.5, button: str = "left", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.duration = duration
        self.button = button

    def execute(self) -> bool:
        pyautogui.dragTo(self.x, self.y,
                         duration=self.duration, button=self.button)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y,
                "duration": self.duration, "button": self.button}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.duration = params.get("duration", 0.5)
        self.button = params.get("button", "left")

    def get_display_name(self) -> str:
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
        pyautogui.scroll(self.clicks, self.x, self.y)
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
