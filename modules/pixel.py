"""
Pixel Checker – Fast pixel color checking using Windows API.

Uses Win32 GetPixel() directly from screen DC instead of
capturing full screen, making it orders of magnitude faster
for single-pixel checks.

Actions: CheckPixelColor, WaitForColor
"""

import ctypes
import logging
import time
from typing import Any, Optional

from core.action import Action, register_action

logger = logging.getLogger(__name__)

# Windows API handles
_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32


class PixelChecker:
    """
    Fast pixel color checking via Windows GDI.

    Usage:
        pc = PixelChecker()
        r, g, b = pc.get_pixel(100, 200)
        if pc.check_color(100, 200, 255, 0, 0, tolerance=15):
            print("Red pixel detected!")
    """

    def __init__(self) -> None:
        self._hdc: int = _user32.GetDC(0)  # Screen DC

    def __del__(self) -> None:
        self.release()

    def release(self) -> None:
        """Explicitly release GDI screen DC."""
        if hasattr(self, "_hdc") and self._hdc:
            _user32.ReleaseDC(0, self._hdc)
            self._hdc = 0

    def get_pixel(self, x: int, y: int) -> tuple[int, int, int]:
        """Get (R, G, B) at screen coordinates."""
        color = _gdi32.GetPixel(self._hdc, x, y)
        r = color & 0xFF
        g = (color >> 8) & 0xFF
        b = (color >> 16) & 0xFF
        return r, g, b

    def check_color(
        self, x: int, y: int,
        r: int, g: int, b: int,
        tolerance: int = 10,
    ) -> bool:
        """Check if pixel matches color within tolerance."""
        pr, pg, pb = self.get_pixel(x, y)
        return (
            abs(pr - r) <= tolerance
            and abs(pg - g) <= tolerance
            and abs(pb - b) <= tolerance
        )

    def wait_for_color(
        self, x: int, y: int,
        r: int, g: int, b: int,
        tolerance: int = 10,
        timeout_ms: int = 10000,
        poll_ms: int = 100,
        appear: bool = True,
    ) -> bool:
        """Wait for pixel color to appear or disappear."""
        deadline = time.perf_counter() + timeout_ms / 1000.0
        interval = poll_ms / 1000.0

        while time.perf_counter() < deadline:
            matches = self.check_color(x, y, r, g, b, tolerance)
            if (appear and matches) or (not appear and not matches):
                return True
            time.sleep(interval)
        return False


# Global instance (lazy)
_checker: Optional[PixelChecker] = None


def get_pixel_checker() -> PixelChecker:
    global _checker
    if _checker is None:
        _checker = PixelChecker()
        # Register cleanup with MemoryManager for 24/7 safety
        try:
            from core.memory_manager import MemoryManager
            mm = MemoryManager.instance()
            mm.register_cleanup(_checker.release)
        except Exception:
            pass
    return _checker


# ---------------------------------------------------------------------------
# Action wrappers
# ---------------------------------------------------------------------------

@register_action("check_pixel_color")
class CheckPixelColor(Action):
    """Check if a pixel matches an expected color."""

    def __init__(self, x: int = 0, y: int = 0,
                 r: int = 0, g: int = 0, b: int = 0,
                 tolerance: int = 10, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.r = r
        self.g = g
        self.b = b
        self.tolerance = tolerance
        self._result = False

    def execute(self) -> bool:
        pc = get_pixel_checker()
        self._result = pc.check_color(
            self.x, self.y, self.r, self.g, self.b, self.tolerance
        )
        logger.info(
            "Pixel(%d,%d) check RGB(%d,%d,%d) tol=%d → %s",
            self.x, self.y, self.r, self.g, self.b,
            self.tolerance, self._result,
        )
        return True

    @property
    def matched(self) -> bool:
        return self._result

    def _get_params(self) -> dict[str, Any]:
        return {
            "x": self.x, "y": self.y,
            "r": self.r, "g": self.g, "b": self.b,
            "tolerance": self.tolerance,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.r = params.get("r", 0)
        self.g = params.get("g", 0)
        self.b = params.get("b", 0)
        self.tolerance = params.get("tolerance", 10)

    def get_display_name(self) -> str:
        return f"Pixel ({self.x},{self.y}) = RGB({self.r},{self.g},{self.b})"


@register_action("wait_for_color")
class WaitForColor(Action):
    """Wait until a pixel reaches a target color."""

    def __init__(self, x: int = 0, y: int = 0,
                 r: int = 0, g: int = 0, b: int = 0,
                 tolerance: int = 10, timeout_ms: int = 10000, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.r = r
        self.g = g
        self.b = b
        self.tolerance = tolerance
        self.timeout_ms = timeout_ms

    def execute(self) -> bool:
        pc = get_pixel_checker()
        found = pc.wait_for_color(
            self.x, self.y, self.r, self.g, self.b,
            self.tolerance, self.timeout_ms,
        )
        if not found:
            logger.warning("WaitForColor timed out at (%d,%d)", self.x, self.y)
        return found

    def _get_params(self) -> dict[str, Any]:
        return {
            "x": self.x, "y": self.y,
            "r": self.r, "g": self.g, "b": self.b,
            "tolerance": self.tolerance,
            "timeout_ms": self.timeout_ms,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.r = params.get("r", 0)
        self.g = params.get("g", 0)
        self.b = params.get("b", 0)
        self.tolerance = params.get("tolerance", 10)
        self.timeout_ms = params.get("timeout_ms", 10000)

    def get_display_name(self) -> str:
        return f"Wait color ({self.x},{self.y}) RGB({self.r},{self.g},{self.b})"
